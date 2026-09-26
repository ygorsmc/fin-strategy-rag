import hashlib
import json
import datetime
import subprocess
import zipfile
from pathlib import Path

import duckdb
import pandas as pd

from scripts import auditar_rank03b_consumo_operacional as a
from scripts import fonte_zip_cvm as fz
from scripts import gates_painel_pesquisa_rank03b as g
from scripts import painel_pesquisa_rank03b as pp


def proibido(*args, **kwargs):
    raise AssertionError('revisao nao autoriza calcular o rotulo')


a._somas_do_rotulo = proibido
root = Path.cwd()
base = root / 'artefatos/painel_pesquisa_rank03b'
con = duckdb.connect(':memory:')
hashes = fz.extrair(con)
hash_compartilhado = pp.preparar_universo(con)
correcoes = g.carregar_correcoes(g.CORRECOES)
p = pp.construir(con, correcoes)
falsificacoes = g.verificar_falsificacoes(p, con)
decididos = g.documentos_decididos(g.ADJUDICACAO)
medicao = g.medir(p, decididos)
gravado = json.loads((base / 'gates_g0_g1.json').read_text())
verificacao = json.loads((base / 'verificacoes_revisao_final.json').read_text())
normalizado = json.loads(json.dumps(medicao, default=str))
saida = {
    'zips_conferidos': len(hashes),
    'compartilhado_sha256': hash_compartilhado,
    'digest_reconstruido': p.digest,
    'digest_identico_ao_gate': p.digest == gravado['digest_do_painel'],
    'falsificacoes': falsificacoes,
    'gate_cadeia_identica': normalizado['cadeia'] == gravado['cadeia'],
    'veredito_reproduzido': normalizado['veredito'],
    'g0_3_saltos': normalizado['cadeia'][0]['g0_3_saltos_de_escala'],
    'g1_observacoes': normalizado['cadeia'][1]['observacoes'],
    'g1_companhias': normalizado['cadeia'][1]['companhias'],
    'g05_publicado': normalizado['cadeia'][0]['diagnostico_g0_5_proposto'],
}
con.execute("ATTACH 'artefatos/painel_pesquisa_rank03b/painel.duckdb' AS salvo (READ_ONLY)")
diferencas = {}
for nome in pp.TABELAS:
    df = pd.DataFrame(getattr(p, nome))
    con.register('_tabela_reconstruida', df)
    diferencas[nome] = con.execute(f'''
        SELECT count(*) FROM (
          (SELECT * FROM _tabela_reconstruida EXCEPT ALL SELECT * FROM salvo.{nome})
          UNION ALL
          (SELECT * FROM salvo.{nome} EXCEPT ALL SELECT * FROM _tabela_reconstruida)
        )
    ''').fetchone()[0]
    con.unregister('_tabela_reconstruida')
saida['diferencas_linhas_persistidas'] = diferencas
sha_manifesto = hashlib.sha256((base / 'manifesto_painel.json').read_bytes()).hexdigest()
saida['verificacao_manifesto_painel'] = {
    'registrado': verificacao['painel_sha256_do_manifesto'],
    'atual': sha_manifesto,
    'confere': verificacao['painel_sha256_do_manifesto'] == sha_manifesto,
}
saida['hashes_codigo_verificacao'] = {
    nome: hashlib.sha256((root / nome).read_bytes()).hexdigest() == esperado
    for nome, esperado in verificacao['codigo_sha256'].items()
}
validos = [t for t in p.fco_trimestral if t['estado'] == 'valido']
omitidos = []
for t in validos:
    ds = set(t['escalas_declaradas'].split('+'))
    aps = set(t['escalas_aplicadas'].split('+'))
    sem_veredito = any(
        (t['cd_cvm'], o['conjunto'], o['dt_refer'], int(o['versao'])) not in decididos
        for o in json.loads(t['operandos'])
    )
    if len(ds) == 1 and len(aps) > 1 and sem_veredito:
        omitidos.append({k: t[k] for k in ('cd_cvm', 'trimestre', 'dt_ini', 'dt_fim',
                                          'escalas_declaradas', 'escalas_aplicadas')})
saida['g05_classe_nao_contada'] = omitidos
saida['g05_classe_nao_contada_companhias'] = len({t['cd_cvm'] for t in omitidos})

# Contagens de disponibilidade: não seleciona nem agrega desfecho.
cegos = [t for t in validos if t['disponivel_em_v1'] < t['disponivel_em']]
datas_cadastro = {}
for cd, d in con.execute('SELECT DISTINCT cd_cvm, dt_receb FROM cadastro JOIN universo USING(cd_cvm)').fetchall():
    datas_cadastro.setdefault(cd, set()).add(d)
pares = [(t['cd_cvm'], d) for t in cegos for d in datas_cadastro[t['cd_cvm']]
         if t['disponivel_em_v1'] <= d < t['disponivel_em']]
saida['p2_pares_trimestre_decisao'] = len(pares)
saida['p2_decisoes_distintas'] = len(set(pares))

# Disponibilidade da prova de escala, e não só do operando numérico.
cadastro = dict(con.execute(
    'SELECT id_doc, max(dt_receb) FROM cadastro GROUP BY id_doc'
).fetchall())
herdadas = [r for r in correcoes.values() if r['base'] == 'herdada_trecho']
limites = {
    r['id_doc']: max(cadastro[pt['id_doc']] for pt in json.loads(r['pontas']))
    for r in herdadas
}
antecipados = [r for r in p.ativo if r['id_doc'] in limites
               and r['disponivel_em'] < limites[r['id_doc']]]
limites_fco = {}
for t in validos:
    ds = [limites[o['id_doc']] for o in json.loads(t['operandos'])
          if o['id_doc'] in limites]
    if ds:
        limites_fco[(t['cd_cvm'], t['trimestre'])] = max(ds)
limites_ativo = {
    (r['cd_cvm'], r['trimestre']): limites[r['id_doc']]
    for r in p.ativo if r['id_doc'] in limites and r['estado'] == 'valido'
}
amostra, _ = a.construir_amostra(g.linhas_fco(p), g.linhas_ativo(p), calcular_rotulo=False)
afetadas = []
for obs in amostra:
    cd, d = obs['cd_cvm'], datetime.date.fromisoformat(obs['D'])
    jf = any(limites_fco.get((cd, j['trimestre']), datetime.date.min) > d
             for j in obs['linhagem']['janela'])
    ja = limites_ativo.get((cd, obs['linhagem']['ativo']['trimestre']), datetime.date.min) > d
    if jf or ja:
        afetadas.append((cd, obs['D'], jf, ja))
saida['heranca_pit'] = {
    'correcoes': len(herdadas),
    'companhias': len({r['cd_cvm'] for r in herdadas}),
    'ativos_antecipados': len(antecipados),
    'dias_min': min((limites[r['id_doc']] - r['disponivel_em']).days for r in antecipados),
    'dias_max': max((limites[r['id_doc']] - r['disponivel_em']).days for r in antecipados),
    'amostra_cega_afetada': afetadas,
}

# Contraprovas exclusivamente sintéticas do instrumento, não do alvo real.
x, y = [0] * 400 + list(range(1, 101)), [i % 2 for i in range(500)]
quintis = a.amplitude_por_quintis(x, y)
saida['quintis_sinteticos'] = {
    'tamanhos': [f['n'] for f in quintis['faixas']], 'amplitude': quintis['amplitude']
}
saida['t2_sintetico_auc_zero'] = a.teste_t2(
    [{'cd_cvm': 'A', 's': 0, 'y': 1}, {'cd_cvm': 'A', 's': 1, 'y': 0}], 's', 1)

# Só páginas de balanço; nenhum FCO ou resultado do alvo é publicado.
pacote = base / 'rad/brutos/152742.zip'
with zipfile.ZipFile(pacote) as z:
    pdf = z.read('152742_027570_16092026084005.pdf')
paginas = {}
for numero in (11, 30):
    texto = subprocess.run(
        ['pdftotext', '-f', str(numero), '-l', str(numero), '-layout', '-', '-'],
        input=pdf, capture_output=True, check=True,
    ).stdout.decode()
    paginas[str(numero)] = [l.strip() for l in texto.splitlines()
                            if any(s in l for s in ('Reais Unidade', 'milhares de reais',
                                                     'Ativo Total', 'TOTAL DO ATIVO'))]
esc = next(r for r in p.ativo if r['id_correcao'] == 'ESC-0101')
saida['esc_0101'] = {
    'sha256_pacote': hashlib.sha256(pacote.read_bytes()).hexdigest(),
    'paginas_fisicas': paginas,
    'painel': {k: esc[k] for k in ('id_correcao', 'cd_cvm', 'dt_fim', 'valor_bruto',
                                 'valor_reais', 'escala_declarada', 'escala_aplicada')},
}
print(json.dumps(saida, indent=2, ensure_ascii=False, default=str))
con.close()

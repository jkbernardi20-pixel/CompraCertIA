"""Testes do MVP: recorrência, recomendação, economia e os princípios fixos."""

import unittest
from datetime import date

from unittest import mock

from compracertia import analise, compartilhar, db, importacao, relatorio


def _banco():
    return db.conectar(":memory:")


def _compras_de_cafe(conn, n=12, preco_pacote=18.90):
    """Uma compra por mês ao longo de um ano, 1 pacote de 500g cada."""
    for mes in range(1, n + 1):
        db.registrar_compra(
            conn,
            item="Café",
            marca="Marca Cara",
            preco=preco_pacote,
            quantidade=1,
            unidade="500g",
            data=f"2025-{mes:02d}-10",
            categoria="A",
        )


class TestArmazenamento(unittest.TestCase):
    def test_categoria_exigida_apenas_no_primeiro_registro(self):
        conn = _banco()
        with self.assertRaises(ValueError):
            db.registrar_compra(conn, "Leite", "Piracanjuba", 5.99, 1, "1L")
        db.registrar_compra(conn, "Leite", "Piracanjuba", 5.99, 1, "1L", categoria="A")
        # Segunda compra não precisa repetir a categoria; nome é case-insensitive.
        db.registrar_compra(conn, "leite", "Italac", 5.49, 2, "1L")
        itens = db.listar_itens(conn)
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["n_compras"], 2)

    def test_alternativa_recusada_para_categoria_b(self):
        conn = _banco()
        db.registrar_compra(conn, "Cerveja", "Heineken", 35.0, 1, "12un", categoria="B")
        with self.assertRaises(ValueError):
            db.registrar_alternativa(conn, "Cerveja", "Genérica", 20.0, "12un")

    def test_alternativa_exige_item_existente(self):
        conn = _banco()
        with self.assertRaises(ValueError):
            db.registrar_alternativa(conn, "Azeite", "Gallo", 30.0, "500ml")


class TestAnalise(unittest.TestCase):
    def test_recorrencia_exige_minimo_de_compras(self):
        conn = _banco()
        db.registrar_compra(conn, "Pão", "Wickbold", 8.0, 1, "un", "2025-01-01", "A")
        db.registrar_compra(conn, "Pão", "Wickbold", 8.0, 1, "un", "2025-02-01")
        self.assertEqual(analise.identificar_recorrentes(conn), [])
        db.registrar_compra(conn, "Pão", "Wickbold", 8.0, 1, "un", "2025-03-01")
        recorrentes = analise.identificar_recorrentes(conn)
        self.assertEqual([r.item for r in recorrentes], ["Pão"])
        self.assertEqual(recorrentes[0].n_compras, 3)

    def test_economia_anualizada_pela_frequencia_real(self):
        conn = _banco()
        _compras_de_cafe(conn, n=12, preco_pacote=18.90)
        db.registrar_alternativa(
            conn, "Café", "Alternativa Boa", 12.90, "500g", "100% arábica, torra média"
        )
        (rec,) = analise.identificar_recorrentes(conn)
        r = analise.recomendar(conn, rec)
        self.assertIsNotNone(r)
        self.assertEqual(r.marca_alternativa, "Alternativa Boa")
        # 12 pacotes em 334 dias -> ~13,1 pacotes/ano * R$6,00 de diferença.
        esperado = (18.90 - 12.90) * 12 * 365 / 334
        self.assertAlmostEqual(r.economia_anual, esperado, places=2)
        self.assertIn("100% arábica", r.justificativa)
        self.assertIn("R$", r.justificativa)

    def test_nunca_recomenda_categoria_b(self):
        conn = _banco()
        for mes in range(1, 7):
            db.registrar_compra(
                conn, "Vinho", "Reserva", 60.0, 1, "750ml", f"2025-{mes:02d}-05", "B"
            )
        (rec,) = analise.identificar_recorrentes(conn)
        self.assertEqual(rec.categoria, "B")
        self.assertIsNone(analise.recomendar(conn, rec))

    def test_sem_recomendacao_quando_alternativa_nao_e_mais_barata(self):
        conn = _banco()
        _compras_de_cafe(conn)
        db.registrar_alternativa(conn, "Café", "Mais Cara", 25.0, "500g")
        (rec,) = analise.identificar_recorrentes(conn)
        self.assertIsNone(analise.recomendar(conn, rec))

    def test_nao_compara_unidades_diferentes(self):
        conn = _banco()
        _compras_de_cafe(conn)  # compras em 500g
        db.registrar_alternativa(conn, "Café", "Pacotão", 22.0, "1kg")
        (rec,) = analise.identificar_recorrentes(conn)
        self.assertEqual(rec.unidade, "500g")
        # R$22/kg seria mais barato por grama, mas a unidade não bate:
        # o MVP só compara pacotes iguais para não distorcer a conta.
        self.assertIsNone(analise.recomendar(conn, rec))

    def test_preco_medio_ignora_unidade_minoritaria(self):
        conn = _banco()
        _compras_de_cafe(conn, n=5, preco_pacote=18.90)
        db.registrar_compra(conn, "Café", "Pacotão", 30.0, 1, "1kg", "2025-06-15")
        (rec,) = analise.identificar_recorrentes(conn)
        self.assertEqual(rec.unidade, "500g")
        self.assertEqual(rec.n_compras, 5)
        self.assertAlmostEqual(rec.preco_medio, 18.90)


class TestEdicaoRemocao(unittest.TestCase):
    def test_editar_corrige_campos(self):
        conn = _banco()
        cid = db.registrar_compra(conn, "Leite", "Italac", 5.99, 1, "1L", "2025-01-01", "A")
        db.editar_compra(conn, cid, preco=4.49, quantidade=6)
        c = db.obter_compra(conn, cid)
        self.assertAlmostEqual(c["preco"], 4.49)
        self.assertEqual(c["quantidade"], 6)
        self.assertEqual(c["marca"], "Italac")  # inalterado

    def test_editar_ignora_none_e_valida(self):
        conn = _banco()
        cid = db.registrar_compra(conn, "Leite", "Italac", 5.99, 1, "1L", "2025-01-01", "A")
        with self.assertRaises(ValueError):
            db.editar_compra(conn, cid)  # nada informado
        with self.assertRaises(ValueError):
            db.editar_compra(conn, cid, preco=-1)
        with self.assertRaises(ValueError):
            db.editar_compra(conn, 999, marca="X")  # compra inexistente

    def test_remover(self):
        conn = _banco()
        cid = db.registrar_compra(conn, "Leite", "Italac", 5.99, 1, "1L", "2025-01-01", "A")
        db.remover_compra(conn, cid)
        self.assertIsNone(db.obter_compra(conn, cid))
        with self.assertRaises(ValueError):
            db.remover_compra(conn, cid)  # já não existe


class TestImportacaoCSV(unittest.TestCase):
    def test_importa_linhas_validas(self):
        conn = _banco()
        csv_texto = (
            "item,marca,preco,quantidade,unidade,data,categoria\n"
            "Café,Melitta,18.90,1,500g,2025-01-10,A\n"
            "Café,Melitta,18.90,1,500g,2025-02-10,\n"
            "Cerveja,Heineken,42.00,1,12un,2025-01-05,B\n"
        )
        res = importacao.importar_csv(conn, csv_texto)
        self.assertEqual(res.importadas, 3)
        self.assertEqual(res.erros, [])
        self.assertEqual(len(db.listar_compras(conn, "Café")), 2)

    def test_linha_invalida_nao_interrompe(self):
        conn = _banco()
        csv_texto = (
            "item,marca,preco,categoria\n"
            "Café,Melitta,18.90,A\n"
            "Vinho,Miolo,55.00,\n"          # item novo sem categoria -> erro
            ",Sem Item,10.00,A\n"           # falta item -> erro
            "Azeite,Gallo,notanumber,A\n"   # preço inválido -> erro
            "Pão,Wickbold,8.00,A\n"
        )
        res = importacao.importar_csv(conn, csv_texto)
        self.assertEqual(res.importadas, 2)
        self.assertEqual(res.total_erros, 3)
        # números de linha do arquivo (cabeçalho = 1)
        self.assertEqual([n for n, _ in res.erros], [3, 4, 5])

    def test_cabecalho_obrigatorio(self):
        conn = _banco()
        with self.assertRaises(ValueError):
            importacao.importar_csv(conn, "item,marca\nCafé,Melitta\n")


class TestCodigoBarras(unittest.TestCase):
    def test_registrar_com_codigo_memoriza_produto(self):
        conn = _banco()
        db.registrar_compra(
            conn, "Café", "Melitta", 18.90, 1, "500g",
            "2025-01-10", "A", codigo="7891234567890",
        )
        achado = db.buscar_codigo(conn, "7891234567890")
        self.assertIsNotNone(achado)
        self.assertEqual(achado["item"], "Café")
        self.assertEqual(achado["marca"], "Melitta")
        self.assertEqual(achado["unidade"], "500g")
        self.assertEqual(achado["categoria"], "A")

    def test_codigo_desconhecido(self):
        conn = _banco()
        self.assertIsNone(db.buscar_codigo(conn, "0000000000000"))

    def test_recompra_atualiza_associacao(self):
        conn = _banco()
        db.registrar_compra(conn, "Café", "Marca A", 18.90, 1, "500g",
                            "2025-01-10", "A", codigo="789")
        # Mesmo código, marca diferente numa compra posterior: atualiza.
        db.registrar_compra(conn, "Café", "Marca B", 17.50, 1, "500g",
                            "2025-02-10", codigo="789")
        achado = db.buscar_codigo(conn, "789")
        self.assertEqual(achado["marca"], "Marca B")
        # Não duplica: um código -> um produto.
        self.assertEqual(len(db.listar_codigos(conn)), 1)

    def test_salvar_codigo_direto(self):
        conn = _banco()
        db.salvar_codigo(conn, "555", "Leite", "Italac", "1L", categoria="A")
        achado = db.buscar_codigo(conn, "555")
        self.assertEqual(achado["item"], "Leite")
        # Item novo sem categoria deve falhar (mesma regra do registro).
        with self.assertRaises(ValueError):
            db.salvar_codigo(conn, "666", "Novo", "X", "un")

    def test_codigo_vazio_ignorado_no_registro(self):
        conn = _banco()
        db.registrar_compra(conn, "Café", "Melitta", 18.90, 1, "500g",
                            "2025-01-10", "A", codigo="   ")
        self.assertEqual(db.listar_codigos(conn), [])


class TestCompartilhar(unittest.TestCase):
    def test_regex_extrai_url_publica(self):
        linha = (
            "2025-01-01T00:00:00Z INF +---+\n"
            "| https://exemplo-teste-abc.trycloudflare.com |"
        )
        achada = compartilhar.URL_PUBLICA_RE.search(linha)
        self.assertIsNotNone(achada)
        self.assertEqual(
            achada.group(0), "https://exemplo-teste-abc.trycloudflare.com"
        )

    def test_regex_ignora_outras_urls(self):
        self.assertIsNone(
            compartilhar.URL_PUBLICA_RE.search("veja https://github.com/x/y")
        )

    def test_erro_claro_sem_cloudflared(self):
        with mock.patch("compracertia.compartilhar.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                compartilhar.compartilhar(porta=8000)
        self.assertIn("cloudflared", str(ctx.exception))


class TestRelatorio(unittest.TestCase):
    def test_relatorio_completo(self):
        conn = _banco()
        _compras_de_cafe(conn)
        db.registrar_alternativa(
            conn, "Café", "Alternativa Boa", 12.90, "500g", "100% arábica"
        )
        for mes in range(1, 5):
            db.registrar_compra(
                conn, "Cerveja", "IPA Local", 40.0, 1, "6un", f"2025-{mes:02d}-20", "B"
            )
        for mes in range(1, 5):
            db.registrar_compra(
                conn, "Azeite", "Gallo", 35.0, 1, "500ml", f"2025-{mes:02d}-25", "A"
            )
        texto = relatorio.gerar_relatorio(conn, hoje=date(2026, 1, 15))
        self.assertIn("Café", texto)
        self.assertIn("Alternativa Boa", texto)
        self.assertIn("economia estimada", texto)
        # Azeite é recorrente A sem alternativa cadastrada.
        self.assertIn("Azeite", texto)
        self.assertIn("Sem alternativa cadastrada", texto)
        # Cerveja aparece só como Categoria B, sem recomendação.
        self.assertIn("Categoria B", texto)
        self.assertIn("Cerveja", texto)
        self.assertNotIn("experimentar", texto.split("Categoria B")[1])

    def test_relatorio_sem_dados(self):
        conn = _banco()
        texto = relatorio.gerar_relatorio(conn)
        self.assertIn("Nenhum item recorrente", texto)


if __name__ == "__main__":
    unittest.main()

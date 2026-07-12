"""Testes do MVP: recorrência, recomendação, economia e os princípios fixos."""

import unittest
from datetime import date

from compracertia import analise, db, relatorio


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

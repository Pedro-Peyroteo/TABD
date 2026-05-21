# -*- coding: utf-8 -*-
"""
take_screenshots.py
Captura automaticamente os 6 screenshots do FitMap em localhost:8000
e guarda-os em docs/screenshots/ prontos para inserir no relatorio.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "screenshots"
OUT.mkdir(exist_ok=True)

BASE = "http://localhost:8000"

def wait(ms=1500):
    time.sleep(ms / 1000)


def capture(page, filename, description):
    path = str(OUT / filename)
    page.screenshot(path=path, full_page=False)
    print(f"  OK  {filename}  ({description})")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        page = ctx.new_page()

        # ── 1. LANDING PAGE ─────────────────────────────────────────────────
        print("1/6  Landing page...")
        page.goto(BASE, wait_until="networkidle")
        wait(2000)
        capture(page, "01_landing.png", "landing page com estatisticas")

        # ── 2. MAPA NACIONAL ────────────────────────────────────────────────
        print("2/6  Mapa nacional...")
        # clicar em "Ver no mapa"
        page.click("#lnd-btn")
        wait(3000)
        # aguardar marcadores (camada de mapa)
        page.wait_for_selector("#map", state="visible")
        wait(2000)
        capture(page, "02_mapa_portugal.png", "mapa nacional completo")

        # ── 3. LISBOA - GINASIOS ────────────────────────────────────────────
        print("3/6  Lisboa - Ginasios...")
        # clicar em Lisboa na lista de cidades
        page.evaluate("""
            () => {
                const items = document.querySelectorAll('#city-list .city-item');
                for (const item of items) {
                    if (item.textContent.includes('Lisboa')) { item.click(); break; }
                }
            }
        """)
        wait(1500)
        # clicar no filtro "Ginasio"
        page.evaluate("""
            () => {
                const btns = document.querySelectorAll('#cat-filters button, #cat-filters .filter-btn');
                for (const b of btns) {
                    if (b.textContent.toLowerCase().includes('gin')) { b.click(); break; }
                }
            }
        """)
        wait(2000)
        capture(page, "03_lisboa_ginasios.png", "Lisboa filtrado por Ginasios")

        # ── 4. GEONEEAR - RAIO 3 KM ─────────────────────────────────────────
        print("4/6  GeoNear - raio...")
        # limpar filtros e simular right-click no centro do mapa (Lisboa)
        page.evaluate("""
            () => {
                // disparar evento contextmenu no centro do mapa
                const map = document.getElementById('map');
                const rect = map.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const ev = new MouseEvent('contextmenu', {
                    bubbles: true, cancelable: true,
                    clientX: cx, clientY: cy
                });
                map.dispatchEvent(ev);
            }
        """)
        wait(3000)
        capture(page, "04_geonear_raio.png", "painel geoNear 50 resultados por distancia")

        # ── 5. ROTA + EVENTOS ────────────────────────────────────────────────
        print("5/6  Rota + eventos...")
        # clicar no primeiro marcador visivel para abrir painel
        page.evaluate("""
            () => {
                const markers = document.querySelectorAll('.leaflet-marker-icon');
                if (markers.length > 0) markers[0].click();
            }
        """)
        wait(1500)
        # clicar em "Calcular rota"
        page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.textContent.includes('Calcular rota') || b.textContent.includes('rota')) {
                        b.click(); break;
                    }
                }
            }
        """)
        wait(4000)
        capture(page, "05_rota_eventos.png", "rota calculada + painel de eventos")

        # ── 6. DETALHE INSTALACAO ────────────────────────────────────────────
        print("6/6  Detalhe instalacao...")
        # fechar rota e abrir outro marcador
        page.evaluate("""
            () => {
                const close = document.querySelector('.route-close, #panel-close');
                if (close) close.click();
                // re-abrir painel lateral se fechado
                const markers = document.querySelectorAll('.leaflet-marker-icon');
                if (markers.length > 1) markers[1].click();
                else if (markers.length > 0) markers[0].click();
            }
        """)
        wait(2000)
        capture(page, "06_detalhe_instalacao.png", "painel detalhe com modalidades e eventos")

        browser.close()
        print(f"\nConcluido! 6 imagens guardadas em: {OUT}")


if __name__ == "__main__":
    main()

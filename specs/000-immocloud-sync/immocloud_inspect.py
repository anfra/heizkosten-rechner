"""
Diagnose-Skript: Öffnet das Zähler-Anlegen-Formular und gibt alle
sichtbaren Felder, Dropdown-Optionen und Tree-Knoten aus.

Nutzt den vorhandenen Brave-Browser mit bestehender Login-Session.

Verwendung:
    python immocloud_inspect.py
"""
import asyncio
import os
from playwright.async_api import async_playwright

BASE_URL = "https://app.immocloud.de"
BRAVE_EXECUTABLE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
BRAVE_USER_DATA  = os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser")


async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=BRAVE_USER_DATA,
            executable_path=BRAVE_EXECUTABLE,
            headless=False,
            slow_mo=200,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # --- Prüfen ob eingeloggt ---
        await page.goto(f"{BASE_URL}/meters")
        await page.wait_for_load_state("networkidle")
        if "/login" in page.url:
            print("Nicht eingeloggt – bitte manuell im Browser einloggen und Enter drücken...")
            input()
            await page.goto(f"{BASE_URL}/meters")
            await page.wait_for_load_state("networkidle")
        print(f"Eingeloggt. URL: {page.url}")

        # --- Zähler-Anlegen-Dialog öffnen ---
        await page.goto(f"{BASE_URL}/meters")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(500)
        await page.get_by_role("button", name="Neuen Zähler anlegen", exact=True).click()
        await page.wait_for_url(f"{BASE_URL}/meters/add", timeout=10_000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1500)

        print("\n" + "="*60)
        print("FORMULAR-INSPEKTION")
        print("="*60)

        # --- Alle Labels ---
        labels = await page.locator("label").all_text_contents()
        print(f"\n[Labels] ({len(labels)} gefunden):")
        for l in labels:
            print(f"  • {l.strip()!r}")

        # --- Alle Inputs ---
        inputs = await page.locator("input").all()
        print(f"\n[Inputs] ({len(inputs)} gefunden):")
        for inp in inputs:
            t = await inp.get_attribute("type") or "text"
            ph = await inp.get_attribute("placeholder") or ""
            iid = await inp.get_attribute("id") or ""
            role = await inp.get_attribute("role") or ""
            readonly = await inp.get_attribute("readonly")
            vis = await inp.is_visible()
            print(f"  • id={iid!r} type={t!r} role={role!r} placeholder={ph!r} readonly={readonly} visible={vis}")

        # --- TreeSelect: Panel öffnen ---
        print("\n[TreeSelect] Versuche zu öffnen...")
        tree_container = page.locator("[data-pc-name='treeselect']").first
        if not await tree_container.count():
            tree_container = page.locator(".p-treeselect").first
        if await tree_container.count():
            label_cont = tree_container.locator(".p-treeselect-label-container")
            if await label_cont.count():
                await label_cont.click()
                await page.wait_for_timeout(800)
                tree_labels = await page.locator(".p-treenode-label").all_text_contents()
                print(f"  Knoten ohne Expand ({len(tree_labels)}): {tree_labels}")

                # Alle Toggle-Buttons klicken
                toggles = page.locator(".p-tree-node-toggle-button")
                n = await toggles.count()
                print(f"  Expand-Buttons: {n}")
                for i in range(n):
                    try:
                        await toggles.nth(i).click(timeout=1_500)
                        await page.wait_for_timeout(300)
                    except Exception:
                        pass

                tree_labels_expanded = await page.locator(".p-treenode-label").all_text_contents()
                print(f"  Knoten nach Expand ({len(tree_labels_expanded)}): {tree_labels_expanded}")

                # Checken was im Panel ist (alle li-Elemente)
                all_li = await page.locator(".p-treeselect-overlay li, .p-tree li").all_text_contents()
                print(f"  Alle LI-Texte: {all_li[:30]}")

                # Panel schließen (Escape)
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(400)
        else:
            print("  Kein TreeSelect gefunden!")

        # --- PrimeVue Selects (Dropdowns): alle einzeln öffnen ---
        selects = page.locator("[data-pc-name='select'], .p-select, .p-dropdown")
        n_selects = await selects.count()
        print(f"\n[PrimeVue Selects] {n_selects} gefunden:")
        for i in range(n_selects):
            sel = selects.nth(i)
            sel_label = await sel.inner_text()
            print(f"\n  Select #{i}: aktueller Text = {sel_label.strip()!r}")
            try:
                await sel.click(timeout=2_000)
                await page.wait_for_selector(".p-select-overlay", timeout=3_000)
                await page.wait_for_timeout(400)
                options = await page.locator(".p-select-option").all_text_contents()
                print(f"    Optionen: {options}")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
            except Exception as e:
                print(f"    Fehler beim Öffnen: {e}")

        # --- Autocomplete-Felder ---
        ac_inputs = page.locator(".p-autocomplete input, input[aria-autocomplete]")
        n_ac = await ac_inputs.count()
        print(f"\n[Autocomplete Inputs] {n_ac} gefunden:")
        for i in range(n_ac):
            iid = await ac_inputs.nth(i).get_attribute("id") or ""
            ph = await ac_inputs.nth(i).get_attribute("placeholder") or ""
            print(f"  #{i}: id={iid!r} placeholder={ph!r}")

        print("\n" + "="*60)
        print("Inspektion abgeschlossen. Enter drücken zum Schließen...")
        input()
        await context.close()


asyncio.run(main())

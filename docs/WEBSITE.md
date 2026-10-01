# BLOXEN — WEBSITE

Target: historically faithful July-2015 Roblox web experience with BLOXEN branding that is
honest about its unofficial nature.

## Evidence base

| Artifact | What | Grade | Local |
|---|---|---|---|
| `main___7000c43d73500e63554d81258494fa21_m.css` (81,760 B) | 2015-era CSS bundle; begins `/* ~/CSS/Base/CSS/Roblox.css */` with original path comments preserved | 1 ORIGINAL (file), era-fit 3 | `research/sources/website/trade2015/css/`, served at `/static/css/` |
| `page___454963b97fe545e3b3f2aaf85eef6d4a_m.css` (294,424 B) | 2015-era page CSS bundle | 1 / 3 | same |
| `trade.html` (83,652 B) | 2015 trade page capture: `#header/.rbx-header`, `#navContent`, `#MasterContainer`, `#BodyWrapper`, universal-search markup, `.form-label`, tabs, `FooterPager` | 3 ARCHIVED-NEAR (capture served by a revival host in 2015 style — documented caveat) | `research/sources/website/trade-2015.html`, rendered at `/static/ref-trade-2015.html` |
| `AllCSS-2012-era.css` (273,285 B) | AllCSS.ashx archival (2012-era bundle) — supporting evidence only | 1 / 3 | `research/sources/website/AllCSS-2012-era.css` |
| roblox.xsd | Official RBXLX XML schema (authored by Erik Cassel / Roblox) | 1 | `research/sources/formats/roblox.xsd` |

Note on the trade-page capture: internal URLs reference `watrbx.xyz` (a revival host), so the
HTML structure is treated as **archived near-date evidence (grade 3)**, not original. The CSS
bundles carry original Roblox file-path comments and are treated as **preserved original
material (grade 1)** with era-fit assessed at grade 3.

## Reconstructed layout facts (from the evidence)

- Fixed blue header bar (`.rbx-header`), logo slot max-width **166px** (`#header .rbx-navbar-header{max-width:166px}`)
- Primary nav: **Games · Catalog · Develop · ROBUX** (`hidden-xs hidden-sm col-md-4 col-lg-3`)
- Universal search (`#navbar-universal-search`) with dropdown scopes (People/Games/Catalog/Groups/Library)
- Right nav: Log In / Sign Up (2015 captured markup)
- Content container: `.container-main{max-width:970px}`
- Font: **Source Sans Pro** 300–700 (Google Fonts link in captured `<head>`)
- jQuery 1.11.1 + jquery-migrate 1.2.1 + MicrosoftAjax stack (WebForms-era)
- Footer with legal/disclaimer links

## BLOXEN implementation

- `web/templates/base.html` — page shell reconstructed from the captured header/nav/footer
  markup + preserved CSS bundles
- `web/static/css/bloxen.css` — ONLY the disclosure strip, the BLOXEN wordmark sized to the
  historical logo slot, and honest `MISSING`-labeled thumbnail fallbacks. It does not override
  historical layout dimensions.
- Pages implemented: logged-out Home, logged-in Home (games/friends/recent), Games, Game
  Details (tabs About/Store/Servers + preservation record), Catalog, Catalog Item, Profile,
  Character (avatar editor), Inventory ("My Stuff"), Friends (+requests), Groups, Develop,
  Messages, Search, Login, Register, Account Settings, About/Provenance
- Historical page URLs kept where known (`.aspx` routes: `/User.aspx`, `/My/Character.aspx`,
  `/My/Stuff.aspx`, `/catalog/item.aspx?ID=`, `/Login.aspx`, `/Register.aspx`, `/search/results.aspx`)

## Visual validation

Browser screenshots were captured with headless Chromium (CDP) for every major page and
compared against the rendered historical reference (`/static/ref-trade-2015.html` with the
preserved CSS). Comparison record: `checkpoints/screenshots/`:

- `ref-2015-trade-header.png` — historical header/nav rendered with preserved CSS
- `bloxen-home-loggedout.png`, `bloxen-games.png`, `bloxen-catalog.png`,
  `bloxen-catalog-item.png`, `bloxen-game-details.png`, `bloxen-login.png`

Corrections made from comparison: logo constrained to the 166px historical slot; content
widths held to the evidenced 970px container.

## MISSING (not fabricated)

- Historical logo image → BLOXEN wordmark stand-in (labeled)
- Game/catalog item thumbnails → labeled `thumbnail MISSING — not fabricated`
- Source Sans Pro webfont binaries → local-font fallback CSS (`fonts-source-sans.css`)
- Historical page HTML beyond the trade capture → page bodies are RECONSTRUCTION (grade 4)
  built on the preserved CSS + captured structure; each page carries a provenance tag

## Page provenance policy

Every template footer states the reconstruction nature; per-page provenance tags appear in
page bodies (`bloxen-provenance-tag`). Nothing reconstructed is labeled original.

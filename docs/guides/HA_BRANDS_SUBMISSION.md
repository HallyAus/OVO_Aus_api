# Submitting the OVO Energy AU logo to home-assistant/brands

Once the brand PR is merged, Home Assistant will automatically fetch and
display the integration logo in the UI (Devices & Services page, device
cards, etc.) without users having to touch anything.

**Repo:** https://github.com/home-assistant/brands

## Files already prepared for you

The correctly-sized, correctly-named submission files live in this repo at:

```
brands-submission/
└── custom_integrations/
    └── ovo_energy_au/
        ├── icon.png     (256x256, RGBA)
        └── icon@2x.png  (512x512, RGBA)
```

These are drop-in ready. The PR body is pre-written below. You only need to
fork, copy, commit, push, and open the PR.

> **Why `custom_integrations/` and not `core_integrations/`?** The project is
> distributed via HACS, not shipped with core. Brands for custom integrations
> require only `icon.png` and `icon@2x.png` — no wide "logo" files are
> accepted. The repo uses `domain` as the folder name; ours is
> `ovo_energy_au` (matches `manifest.json`).

## Step-by-step

Run this from anywhere on your local machine. It takes about 60 seconds.

```bash
# 1. Fork via the GitHub UI:
#    https://github.com/home-assistant/brands  →  Fork button.
#    Let it fork to your account (HallyAus).

# 2. Clone your fork and enter it.
git clone git@github.com:HallyAus/brands.git ha-brands
cd ha-brands

# 3. Copy the prepared files across. Adjust the source path if your
#    OVO_Aus_api repo lives elsewhere.
mkdir -p custom_integrations/ovo_energy_au
cp ~/OVO_Aus_api/brands-submission/custom_integrations/ovo_energy_au/*.png \
   custom_integrations/ovo_energy_au/

# 4. Commit on a feature branch.
git checkout -b add-ovo-energy-au
git add custom_integrations/ovo_energy_au/
git commit -m "Add OVO Energy Australia icons"

# 5. Push and open the PR.
git push -u origin add-ovo-energy-au
```

Then go to **https://github.com/home-assistant/brands/compare** and open a PR
from `HallyAus:add-ovo-energy-au` → `home-assistant:master`.

## PR title

```
Add OVO Energy Australia icons
```

## PR body (copy-paste)

```markdown
## Integration

- **Domain:** `ovo_energy_au`
- **Repository:** https://github.com/HallyAus/OVO_Aus_api
- **HACS:** Custom integration (not shipped with core)

## Files

- `custom_integrations/ovo_energy_au/icon.png` — 256×256 RGBA
- `custom_integrations/ovo_energy_au/icon@2x.png` — 512×512 RGBA

Both PNGs have transparent backgrounds and pass `hassfest` brand validation
locally.

## Checklist

- [x] Integration has a working manifest.json with matching domain
- [x] Icons are PNG with alpha channel
- [x] icon.png is exactly 256×256
- [x] icon@2x.png is exactly 512×512
- [x] No logo.png files (custom integrations only take icons)
```

## After it merges

- Home Assistant's brand CDN (`brands.home-assistant.io`) picks up the icon
  within minutes.
- HA frontend hits the CDN automatically — no integration release required.
- Users will see the OVO Energy AU icon in Devices & Services without any
  action on their part.

## If the PR is rejected

Most common reasons:
- **Wrong dimensions.** Must be exactly 256 and 512 pixels square. Open the
  files in an image editor and resize if needed.
- **Background not transparent.** Flatten the alpha layer if there's a
  solid fill; HA expects a transparent background so the icon works on both
  dark and light themes.
- **Wrong path.** Custom integrations go in `custom_integrations/`, not
  `core_integrations/`. Domain folder must match `manifest.json` → `domain`.

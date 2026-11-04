
QUERY: Bambu Lab A1 / A1 mini automatic print ejection gcode push-off loop (Factorian Designs and similar)
## Summary

Automatic print ejection on the Bambu Lab A1 and A1 mini is possible using community-developed G-code, but the solutions found are **experimental modifications, not an official Bambu Lab feature**. They generally work by:

1. Printing one copy of a model.
2. Turning off the heaters and allowing the bed and part to cool.
3. Optionally vibrating the bed to help release the part.
4. Using coordinated toolhead and bed movements to **push the part off the build plate**.
5. Sweeping away debris, then repeating the print body for the next copy.

On both A1 models, the ejection motion primarily uses the **Y-axis moving bed**, rather than moving a gantry-mounted pusher across the bed.

## Main projects and guides

| Project | What it provides | Notable details |
|---|---|---|
| **Factorian Designs print automation** | A detailed video guide plus downloadable files for the A1 and A1 mini. It is the basis for several other tools. | Intended for producing parts repeatedly—potentially thousands of times—but still requires model-specific configuration. Factorian strongly recommends watching the complete video before using the files and explicitly disclaims liability for printer damage. The guide also points to Nicki Andersen’s G-code/3MF looping tool. [factoriandesigns.com](https://factoriandesigns.com/print-automation-bambu-lab-a1-a1-mini) |
| **Looprint** | A free, browser-based beta utility that turns an already sliced G-code or 3MF file into a multi-copy job with cooldown, push-off and optional sweeping between loops. | It detects the printer, removes the original start/end code, inserts printer-specific code, repeats the print and adds ejection sequences. Its A1/A1-mini logic is based on Factorian’s templates, including Y-axis pushing and Factorian’s “41 mm rule.” [nickiandersen.github.io](https://nickiandersen.github.io/looprint/) Independent coverage describes the same basic workflow: slice once, wrap the print in a loop, add cooldown/ejection and repeat. [fabbaloo.com](https://www.fabbaloo.com/news/new-free-looprint-utility-enables-hands-free-batch-production) |
| **OpenScan InfiniMod** | A more DIY A1-mini demonstration, explaining the G-code structure and providing a Python approach for generating repetitions. | The exported `.gcode.3mf` is treated as a ZIP archive; the relevant file is `Metadata/plate_1.gcode`. Its example cools for roughly an hour, uses `M970` bed-vibration commands, positions the nozzle close to the plate and then uses bed movements to push parts off. It also tilts the printer approximately 20° so released parts can slide into a collection box. [blog.openscan.eu](https://blog.openscan.eu/posts/bambulab-infinimod/) |
| **FarmLoop Stage 1** | Start/end G-code for the A1 and A1 mini, used with additional parts downloaded from MakerWorld. | The G-code is pasted into the printer’s **Machine G-code** settings. The page says it was tested with Bambu Studio 1.10 and A1/A1-mini firmware 01.04, so that compatibility statement should not be assumed to cover later software or firmware. [3d-farmers.com](https://3d-farmers.com/pages/gcodes) |

## Looprint’s practical requirements

For its A1/A1-mini workflow, Looprint specifies that:

- The model should be sliced **with a brim** and positioned at the edge of the bed for ejection.
- Generated **G-code files must be printed from SD card**.
- A generated **3MF should be opened in Bambu Studio and printed directly with “Print Plate”—not sliced again**.
- The A1 mini needs **50 mm of clearance to the left of the bed** for its sweep motion.
- The first loop should be watched closely; because the utility is still beta, Looprint says not to leave the printer unattended. [nickiandersen.github.io](https://nickiandersen.github.io/looprint/)

## Reliability and safety findings

OpenScan’s longer-term experiment shows both the potential and the limitations. It reported **more than 10 kg of material printed, over 100 ejections and roughly 800 hours of mostly uninterrupted printing**, but also numerous failures and near-misses. [blog.openscan.eu](https://blog.openscan.eu/posts/bambulab-infinimod/)

The main variables were:

- **Material and plate:** PLA on textured PEI worked in its setup; PETG on textured PEI did not.
- **Cooldown:** Some parts released after about 20 minutes, while others needed more than 60.
- **Geometry:** Smaller parts generally released more easily. Larger and rounder parts could be harder to remove than parts with sharp corners.
- **Ambient temperature:** Its parts released more readily at approximately 16°C than at 22°C.
- **Mechanical stress:** If a part remains stuck, the printer can push against it until motors skip, producing violent vibration and potentially damaging or accelerating wear on the toolhead and cantilever.

None of the cited workflows describes a sensor-based verification that the plate is actually empty before starting another copy. Consequently, “automatic” or “hands-free” should not be interpreted as safe unattended operation. Factorian’s video additionally warns against negative `G1 Z` moves in the clearing sequence. [youtube.com](https://www.youtube.com/watch?v=SFd0sxN2eqk)

**Best starting point:** watch the full Factorian guide first, then evaluate Looprint for the least manual workflow. Begin with a small PLA test part on textured PEI, run only one or two loops, and supervise the cooldown, ejection and start of the next print. OpenScan is most useful for understanding or customising the underlying G-code; FarmLoop is an alternative if its additional hardware and version requirements fit your setup.
SOURCES:
- Print Automation Bambu Lab A1 & A1 Mini – Factorian Designs https://factoriandesigns.com/print-automation-bambu-lab-a1-a1-mini
- Automate your Bambu Lab A1 & A1 Mini! Free & Easy https://www.youtube.com/watch?v=SFd0sxN2eqk
- Bambu Lab A1 Mini - InfiniMod - Endless 3d printing | OpenScan Blog https://blog.openscan.eu/posts/bambulab-infinimod/
- FarmLoop Stage 1 - Gcodes for A1 + A1 mini – 3D Farmers https://3d-farmers.com/pages/gcodes
- Looprint (Beta) https://nickiandersen.github.io/looprint/
- New Free Looprint Utility Enables Hands-Free Batch Production « Fabbaloo https://www.fabbaloo.com/news/new-free-looprint-utility-enables-hands-free-batch-production

QUERY: 3D printer automated print removal products: plate changers, belt printers, print farm auto-eject (e.g. 3DQue, SwapMod, AutoFarm3D) 2025 2026
## Summary

The 2025–26 products fall into three distinct categories:

1. **Auto-ejection retrofits** reuse the existing bed, typically combining a release surface, cooling, and printer-controlled part clearing.
2. **Plate changers** physically replace the build plate, allowing several jobs to run before anyone handles the printer.
3. **Belt printers** make part removal part of the printer’s basic architecture rather than adding it retrospectively.

The strongest documentation in these search results is for **3DQue/AutoFarm3D**, followed by an independent hands-on report on ChiTu’s **PlateCycler**.

### Product comparison

| Product/approach | How it works | Status and pricing found | Important limitations |
|---|---|---|---|
| **3DQue Auto Ejection + VAAPR** | Parts release from the VAAPR surface as it cools. Bed-slinger kits use a tilt mechanism; CoreXY kits use a “Flexor” to flex the magnetic bed before clearing. No robot is required. | The current CoreXY product listing shows **US$179–329**, depending on configuration. It requires AutoFarm3D software. [3dque.com](https://www.3dque.com/products/auto-ejection) [shop.3dque.com](https://shop.3dque.com/products/printer-automation-kit) | Automatic removal requires auto bed levelling. Enclosures need an exit route so ejected parts do not accumulate inside. [3dque.com](https://www.3dque.com/faq) |
| **3DQue system for enclosed Bambu Lab printers** | Adds an automatic door opener: the system finishes the print, opens the door, clears the part, closes the door, and resets. This is particularly relevant for enclosed printing with ASA, nylon, or PC blends. | Tom’s Hardware reported a **US$129 Bambu Lab kit** in August 2025, including the door opener and special bed surface. That historical price is not directly comparable with the current $179–329 CoreXY listing. [tomshardware.com](https://www.tomshardware.com/3d-printing/new-auto-ejection-tool-for-bambu-lab-print-farms-automatically-ejects-finished-3d-prints-from-the-machine-usd129-kit-includes-auto-door-opener-and-special-bed-surface-for-frictionless-part-ejection) | Official CoreXY support is narrower than the overall marketing might suggest: the FAQ specifically lists **Bambu Lab X1C, P1P and P1S**, while most other CoreXY printers are not officially supported. |
| **AutoFarm3D / AutoPrint3D software** | Provides print queues and coordinates automated removal. AutoFarm3D offers central queueing for multiple printers; AutoPrint3D’s listed functions include removal confirmation, custom release temperatures and removal G-code, and manual or automatic print starting. | Software pricing was not included in the results. AutoFarm3D can also be used in **manual mode without VAAPR or an ejection kit**. [3dque.com](https://www.3dque.com/quinly3d-products/autoprint3d) [3dque.com](https://www.3dque.com/faq) | The software alone does not provide automatic part removal. 3DQue’s “24/7” reliability statement is a vendor claim, and the company itself notes a learning curve. |
| **ChiTu PlateCycler** | An A1 mini add-on that ejects the completed plate and pulls in another. It uses modified plates with front handles and software that adds plate-changing commands to Bambu Studio G-code, principally through Y-axis movements. | In Fabbaloo’s November 2025 hands-on, it held **up to ten plates**, shipped with four, and was expected to launch on **4 December 2025**. Price was then unknown; these results do not confirm subsequent pricing or availability. [fabbaloo.com](https://www.fabbaloo.com/news/hands-on-with-the-platecycler) | Finished plates simply pile up in front of the printer, so a catch box and adequate fall clearance are needed. Fabbaloo warns that fragile parts or delicate structures could be damaged during ejection. |

## Practical interpretation

### 3DQue: best documented for retrofitting an existing farm

3DQue’s main advantage is that it automates printers operators may already own rather than requiring a new printer architecture. VAAPR is advertised for PLA, PETG, ASA, ABS, nylon, polypropylene, polycarbonate, HIPS and supports, with release behaviour depending on material and bed temperature. The current kit also supports installation on many magnetic flex plates. [shop.3dque.com](https://shop.3dque.com/products/printer-automation-kit)

For an enclosed P1S farm, the door opener is significant: simply removing the enclosure door would undermine the temperature control needed for many engineering materials. Nevertheless, buyers should verify the **exact printer model, current kit contents, software cost, enclosure clearances and official support status**, rather than assuming every Bambu or CoreXY configuration is covered.

### PlateCycler: more plate autonomy, but a model-specific mechanical workflow

A plate changer is attractive when each job should start on a fresh plate rather than waiting for and reusing the same surface. PlateCycler’s ten-plate capacity could therefore provide more job-to-job autonomy than simple ejection. However, Fabbaloo’s hands-on report shows that capacity is not the whole story: plate storage, falling parts, catch-bin arrangement and part fragility all affect whether unattended operation is genuinely useful. Its commercial status and price should be reconfirmed because the available review was written before launch.

### Belt printers, and the SwapMod evidence gap

**Belt printers** take the third approach: advancing the belt can carry finished parts away, supporting continuous batches and, on suitable designs, unusually long parts. They avoid a plate-changing mechanism but require a belt-specific printing and slicing workflow, so they are not a drop-in retrofit for a conventional printer farm.

The returned results did **not** contain a current primary source for either a specific 2025–26 belt-printer product or **SwapMod**. Consequently, SwapMod’s present compatibility, capacity, price and shipping status are unverified here; that is not a claim that it is unavailable. Likewise, no current belt-printer pricing or “best buy” claim can responsibly be drawn from this result set.

## Buying takeaway

- **Supported existing printers, especially a Bambu P1S/X1C/P1P farm:** 3DQue is the best-documented retrofit in these results.
- **Bambu A1 mini and multiple robust jobs on separate plates:** PlateCycler is promising, but verify current availability and plan for safe plate collection.
- **SwapMod or a belt printer:** obtain fresh primary-source specifications before comparing them on price or reliability.
- **For every option:** automatic ejection is not complete print-farm autonomy. Failed-print detection, filament replenishment, removal confirmation, part accumulation and safe handling of fragile prints still need consideration.
SOURCES:
- Auto Ejection https://www.3dque.com/products/auto-ejection
- Hands on with the PlateCycler « Fabbaloo https://www.fabbaloo.com/news/hands-on-with-the-platecycler
- New auto ejection tool for Bambu Lab print farms automatically ejects finished 3D prints from the machine — $129 kit includes auto door opener and special bed surface for frictionless part ejection | Tom's Hardware https://www.tomshardware.com/3d-printing/new-auto-ejection-tool-for-bambu-lab-print-farms-automatically-ejects-finished-3d-prints-from-the-machine-usd129-kit-includes-auto-door-opener-and-special-bed-surface-for-frictionless-part-ejection
- AutoPrint3D https://www.3dque.com/quinly3d-products/autoprint3d
- AutoFarm3D™ Auto Part Ejection Kit with VAAPR™ Bed https://shop.3dque.com/products/printer-automation-kit
- FAQ https://www.3dque.com/faq

QUERY: Bambu A1 bed cooldown heat cycle to release PEI print, failure modes of gantry push-off: parts too short, tipping, collisions
## Bottom line

The evidence supports a **normal print-hot → heaters-off → cool → release** cycle for **PLA on textured PEI**, but not a guaranteed release process. I found no strong evidence for repeated reheating/cooling cycles, nor an official Bambu procedure endorsing automatic gantry push-off. Cooling time, material, geometry, and ambient temperature all affect reliability.

## Cooldown and release findings

- The most relevant experiment used an **A1 Mini**, textured PEI, PLA, and a printer tilted about 20°. After printing, the bed and hotend were turned off and the plate was left to cool for roughly an hour before vibration and mechanical ejection. Some objects released after about 20 minutes, while others needed more than 60 minutes. The project achieved 100+ ejections and roughly 800 hours of mostly unattended printing, but also had numerous failures and near-misses. [blog.openscan.eu](https://blog.openscan.eu/posts/bambulab-infinimod/)
- Release was highly variable:
  - **PLA + textured PEI** worked; **PETG + textured PEI** did not.
  - Smaller parts generally released more easily than larger ones.
  - Round parts tended to stick better than sharp-cornered parts.
  - At approximately **16°C ambient**, parts released easily; at **22°C ambient**, they often remained stuck and required repeated pushing. These are room temperatures, not recommended bed setpoints. [blog.openscan.eu](https://blog.openscan.eu/posts/bambulab-infinimod/)
- A separate **P1S** project similarly relied on thermal contraction. Its author found PLA parts were usually loose by the time a textured PEI bed reached about **22°C**, while ABS released around **40°C**. The system monitored bed temperature before operating an external removal gantry. These figures are useful experimental references, but they are **not validated A1 setpoints**. Cooldown time was the main throughput penalty. [johnmonsen.com](https://johnmonsen.com/designing-an-automatic-3d-printer-farm/)
- Printing adhesion temperature should not be confused with release temperature. Bambu’s wiki notes, for example, that PLA uses approximately **55–65°C on a Textured PEI Plate**, versus 35°C on a Cool Plate; selecting the wrong plate profile can cause poor adhesion or warping. [wiki.bambulab.com](https://wiki.bambulab.com/en/filament-acc/filament/print-quality/warping-falling-off-collapsing)

**Practical interpretation:** validate a temperature-and-time window for the exact A1 plate, filament, part geometry, and environment. Bed temperature can gate the removal attempt, but it does **not** prove that the part is loose.

## Gantry push-off failure modes

The short-part and tipping modes below are mechanical design inferences; the collision and printer-damage risks are directly reported in the A1 Mini project.

| Failure mode | What happens | Design implication |
|---|---|---|
| **Part stuck after cooldown** | The gantry pushes against a part that is still firmly adhered, converting a light sweep into a high-force ram. | Use a low-force, compliant pusher with force/current limiting, stall detection, and strictly limited retries. Do not assume a longer push will solve adhesion. |
| **Low-profile part is missed** | If the pusher’s lower edge is above the part, it passes over it. Lowering a rigid blade far enough to catch every short part increases the chance of contacting the PEI sheet or plate edge. | Use a full-width pusher with a low, compliant contact element that does not drag on or scrape the plate, followed by a clear-bed check. |
| **Part tips or rolls instead of sliding** | A tall or narrow part contacted high above its base can topple; it may then wedge against the pusher, roll back onto the printing area, or obstruct other parts. | Push close to the base and provide enough downstream space or a chute to accommodate tipped parts. Do not rely on every part remaining upright. |
| **Collision with printer or stuck parts** | In the A1 Mini nozzle-push method, insufficient release caused motor skipping and violent vibration, with potential damage or accelerated wear to the toolhead and cantilever. An external gantry avoids using the nozzle as a ram but can still collide with the plate, printer motion envelope, or immovable parts. | Keep the toolhead outside the removal mechanism, sequence motion only when the printer is stationary, and abort on excessive resistance. |
| **Incomplete clearing followed by another print** | A missed, tipped, or jammed part remains on the bed and becomes an obstruction during the next cycle. | Verify that the entire build area and exit path are clear before starting another print; bed temperature alone is insufficient verification. |

OpenScan explicitly warns that its modified G-code can severely damage a printer and should only be experimented with under close observation. John Monsen likewise rejected using the printhead to knock parts off because of toolhead wear and calibration concerns, opting instead for a separate removal mechanism. [blog.openscan.eu](https://blog.openscan.eu/posts/bambulab-infinimod/) [johnmonsen.com](https://johnmonsen.com/designing-an-automatic-3d-printer-farm/)

**Recommended architecture:** cool under validated conditions, attempt one gentle release with an independent compliant gantry, stop immediately on abnormal resistance, and verify bed clearance before repeating the print cycle.
SOURCES:
- Bambu Lab A1 Mini - InfiniMod - Endless 3d printing | OpenScan Blog https://blog.openscan.eu/posts/bambulab-infinimod/
- designing an automatic 3D printer farm – John Monsen https://johnmonsen.com/designing-an-automatic-3d-printer-farm/
- User Manual: Bambu Lab A1 Heated Bed https://ae-pic-a1.aliexpress-media.com/kf/Sbc525d12450d455aae8a93e9f36d970eu.pdf
- Model Warping, Falling Off, or Collapsing | Bambu Lab Wiki https://wiki.bambulab.com/en/filament-acc/filament/print-quality/warping-falling-off-collapsing
- Bambu Lab A1 Mini Review: Brush with Perfection https://3dpros.com/printer-content/bambu-lab-a1-mini-review
- Common print quality problems and solutions https://wiki.bambulab.com/en/knowledge-sharing/common-print-quality-problem

QUERY: Headless slicing STL to Bambu .gcode.3mf with BambuStudio or OrcaSlicer command line in Docker, custom machine_end_gcode
## Summary

Headless **STL → Bambu-compatible `.gcode.3mf`** is supported by both Bambu Studio and OrcaSlicer. The main requirements are:

1. Supply complete printer/process/filament profiles.
2. Put your custom **`machine_end_gcode`** in the full machine profile.
3. Slice with `--slice` and export using `--export-3mf`.
4. Verify the generated G-code inside the resulting archive.

### Command-line slicing

Bambu Studio’s documented CLI supports STL/3MF input, profile loading, orientation/arrangement, slicing, and 3MF export. A suitable single-plate STL command is:

```bash
bambu-studio \
  --orient \
  --arrange 1 \
  --load-settings "/cfg/machine.json;/cfg/process.json" \
  --load-filaments "/cfg/filament.json" \
  --slice 1 \
  --debug 2 \
  --export-3mf /out/model.gcode.3mf \
  /in/model.stl
```

Run this inside your container with the input, profiles, and output directory mounted at `/in`, `/cfg`, and `/out`.

Important details:

- `--load-settings` takes the **machine profile first, process profile second**.
- Bambu’s documentation says these should be **full exported configurations**, not minimal profile fragments.
- `--slice 1` slices plate 1; `--slice 0` slices all plates.
- Settings supplied on the command line have highest priority, followed by `--load-settings`/`--load-filaments`, then settings embedded in an input 3MF. [github.com](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage)

OrcaSlicer inherited Bambu Studio’s CLI architecture, so the principal flags—`--slice`, `--load-settings`, `--load-filaments`, `--export-3mf`, and `--pipe`—are generally the same. Replace the executable with the one supplied by your Orca image; Bambuddy’s container, for example, uses `OrcaSlicer-Soft`. However, **Bambu Studio and OrcaSlicer JSON profiles are not reliably drop-in compatible**, so export profiles using the same slicer you intend to run headlessly. [printago.io](https://printago.io/blog/bambu-studio-cli-reference)

## Adding custom `machine_end_gcode`

For a Bambu printer profile, the appropriate place is the **`machine_end_gcode` string in `machine.json`**:

1. Export the full machine profile from the target slicer.
2. Modify only `machine_end_gcode`, preserving the printer’s normal safety, parking, and shutdown sequence unless you intentionally need to change it.
3. JSON-encode the value correctly: multiple G-code lines are normally represented with `\n`, rather than literal unescaped newlines.
4. Mount that patched profile at `/cfg/machine.json` and load it as shown above.

Using the profile file is usually cleaner than passing multiline G-code through shell arguments. It also avoids Docker/shell quoting problems.

After slicing, verify that your commands actually reached the printer G-code:

```bash
unzip -p /out/model.gcode.3mf Metadata/plate_1.gcode | tail -n 100
```

`--export-3mf` does **not** produce raw `.gcode`; it produces a ZIP-based 3MF archive. The sliced G-code is stored as `Metadata/plate_N.gcode`, alongside checksums, slice information, thumbnails, resolved settings, and model geometry. Bambu printers accept this `.gcode.3mf` format directly. [printago.io](https://printago.io/slicer-cli/export-3mf)

Treat custom end G-code as executable printer instructions: incorrect motion, temperature, or fan commands can be unsafe, so validate the generated file before printing.

## Existing Docker option

Bambuddy provides an optional Docker Compose “slicer sidecar” that already packages headless OrcaSlicer and, optionally, Bambu Studio:

```bash
docker compose up -d                 # OrcaSlicer
docker compose --profile bambu up -d # Both slicers
```

Its documented health endpoints are port `3003` for OrcaSlicer and `3001` for Bambu Studio. It accepts STL/3MF slicing jobs and returns a ready-to-print `.gcode.3mf`; internally, its Orca workflow uses essentially the CLI approach above. This is useful if you want an HTTP/UI workflow rather than maintaining slicer dependencies in your own image. [wiki.bambuddy.cool](https://wiki.bambuddy.cool/features/slicer-api/)

**Practical recommendation:** for a Bambu-only automated pipeline with custom end G-code, use Bambu Studio, a patched full `machine.json`, and the CLI command above. Choose OrcaSlicer if you also need its broader printer/profile ecosystem. In either case, inspect `Metadata/plate_1.gcode` in the output to confirm that `machine_end_gcode` was applied.
SOURCES:
- Command Line Usage · bambulab/BambuStudio Wiki · GitHub https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
- Server-Side Slicing - Bambuddy Documentation https://wiki.bambuddy.cool/features/slicer-api/
- Bambu Studio CLI Reference: Headless Slicing from the Command Line | Printago https://printago.io/blog/bambu-studio-cli-reference
- Using Orca Slicer in CLI Mode for Automated G-code Generation · OrcaSlicer/OrcaSlicer · Discussion #8593 · GitHub https://github.com/OrcaSlicer/OrcaSlicer/discussions/8593
- Slicer API (server-side slicing) - BamDude Documentation https://docs.bamdude.top/features/slicer-api/
- --export-3mf — Slicer CLI reference | Printago https://printago.io/slicer-cli/export-3mf

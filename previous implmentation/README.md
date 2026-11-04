
# Auto eject and loop Bambu A1 and A1 mini prints

(Website)[https://auto3dprintwebgui-production.up.railway.app]

Automatically add start/end blocks and duplicate G-code sequences for repeated printing

⚠️ **Warning:** This tool modifies your G-code.3mf file by injecting custom start/end blocks and duplicating the print sequence. Always review the output and test carefully before using on your printer.
## Usage 

[Watch Factorian Designs video first](https://www.youtube.com/watch?v=SFd0sxN2eqk)

- **1. Select Printer**: Choose your printer model (A1 mini or A1)
- **2. Upload 3MF File**: Select your BambuLab-generated `.gcode.3mf` file (see `How to export from bambulab` below)
- **3. Set Duplication**: Choose how many times to repeat the G-code sequence (default=1 for single print)
- **4. Process File**: Click the button to inject start/end blocks and duplicate the pattern
- **5. Download**: Get modified 3MF with `_modified` suffix for printer-ready looping

## Todo
- [x] unzip
- [x] add front back code
- [x] multiply number
- [x] upload gcode
- [x] download
- [x] user description of what happens
- [x] gif on how to upload
- [x] expanded explanation for user
- [x] link to ideo
- [ ] A1 use

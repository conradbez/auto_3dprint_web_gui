import os
import shutil
import zipfile
import glob
import tempfile
from hstream import hs
import base64

hs.markdown(f"# Auto eject and loop Bambu A1 and A1 mini prints")
hs.markdown("Automatically add start/end blocks and duplicate G-code sequences for automated repeated printing")
with hs.html("article", _class="warning", style="border-left: 4px solid #ffc107; background: #fffbe6; padding: 1em; margin-bottom: 1.5em;"):
    hs.markdown("⚠️ **Warning:** This tool modifies your G-code.3mf file by injecting custom start/end blocks and duplicating the print sequence. Always review the output and test carefully before using on your printer.")

with hs.html("details"):
    with hs.html("summary", style="cursor: pointer; font-weight: bold;"):
        hs.text("Usage instructions:")
    hs.markdown('[Watch Factorian Designs video first](https://www.youtube.com/watch?v=SFd0sxN2eqk)')
    hs.markdown("""
    - **1. Select Printer**: Choose your printer model (A1 mini or A1)
    - **2. Upload 3MF File**: Select your BambuLab-generated `.gcode.3mf` file (see `How to export from bambulab` below)
    - **3. Set Duplication**: Choose how many times to repeat the G-code sequence (default=1 for single print)
    - **4. Process File**: Click the button to inject start/end blocks and duplicate the pattern
    - **5. Download**: Get modified 3MF with `_modified` suffix for printer-ready looping
    """)

def process_3mf(uploaded_file, start_block, end_block, repeat_count):
    # Create persistent tmp directory if it doesn't exist
    persistent_tmp = "tmp"
    os.makedirs(persistent_tmp, exist_ok=True)
    
    # Work in a temp directory for processing
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_3mf = os.path.join(tmpdir, "upload.gcode.3mf")
        zip_file = os.path.join(tmpdir, "upload.gcode.zip")
        unzip_dir = os.path.join(tmpdir, "unzipped")
        metadata_dir = os.path.join(unzip_dir, "Metadata")
        
        # Save uploaded file
        with open(orig_3mf, "wb") as f:
            f.write(uploaded_file.read())
        shutil.copyfile(orig_3mf, zip_file)
        
        # Unzip
        with zipfile.ZipFile(zip_file, "r") as z:
            z.extractall(unzip_dir)
        
        # Find gcode file
        gcode_files = glob.glob(os.path.join(metadata_dir, "*.gcode"))
        if not gcode_files:
            return None, "No .gcode file found in Metadata/"
        
        gcode_path = gcode_files[0]
        with open(gcode_path, "r", encoding="utf-8") as f:
            gcode_content = f.read()
        
        # Modify
        block = f"{start_block}\n\n{gcode_content}\n\n{end_block}"
        new_content = "\n\n".join([block] * repeat_count)
        with open(gcode_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        # Re-zip
        out_zip = os.path.join(tmpdir, "modified.zip")
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(unzip_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, unzip_dir)
                    zipf.write(file_path, arcname)
        
        # Save to persistent location BEFORE the temp directory is deleted
        out_3mf = os.path.join(persistent_tmp, "modified_gcode_modified.3mf")
        shutil.move(out_zip, out_3mf)
        
        # Return the persistent file path
        return out_3mf, None

hs.markdown("---")
hs.markdown("## Get going ✈️")

# Printer selection dropdown
hs.markdown("Select printer:")
printer_model = hs.select_box(label=["A1 mini", "A1"], default_value=["A1 mini"])

# Load start/end blocks based on selection
if printer_model == "A1 mini":
    start_file = "Start_A1_Mini.txt"
    end_file = "End_A1_Mini.txt"
else:  # A1
    start_file = "Start_A1.txt"
    end_file = "End_A1.txt"

with open(start_file, "r", encoding="utf-8") as f:
    start_block = f.read()
with open(end_file, "r", encoding="utf-8") as f:
    end_block = f.read()

uploaded_file = hs.file_upload("Upload your gcode.3mf file: (see 'How to export from bambulab' if you're unsure how to do this)")
repeat_count = int(hs.number_input("How many times to duplicate the G-code?", default_value=1, min_value=1, max_value=20))

if uploaded_file and hs.button('Process and Download'):
    with open(f'tmp/{uploaded_file}', 'rb') as file_obj:
        out_3mf, error = process_3mf(file_obj, start_block, end_block, repeat_count)
    if error:
        hs.error(error)
    else:
        with open(out_3mf, 'rb') as f:
            file_content = f.read()
        
        encoded_file = base64.b64encode(file_content).decode('utf-8')
        
        with hs.html("div", style="margin-top: 20px;"):
            with hs.html("a", 
                        href=f'data:application/octet-stream;base64,{encoded_file}', 
                        download='gcode_modified.3mf',
                        style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;"):
                hs.text("📥 Download Modified 3MF")

with hs.html("details"):
    with hs.html("summary", style="cursor: pointer; font-weight: bold;"):
        hs.text("How to export from bambulab")
    with hs.html("img", src="https://raw.githubusercontent.com/conradbez/auto_3dprint_web_gui/refs/heads/main/export_tutorial.gif", alt="How to export from bambulab", style="display: block; width: 100%; height: auto; margin-top: 10px;"):
        pass

with hs.html("details"):
    with hs.html("summary", style="cursor: pointer; font-weight: bold;"):
        hs.text("About")
    hs.markdown("[Github repo](https://github.com/conradbez/auto_3dprint_web_gui/)")
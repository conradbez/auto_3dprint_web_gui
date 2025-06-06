import os
import shutil
import zipfile
import glob
import tempfile
from hstream import hs
import base64

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

# Load start/end blocks once
with open("Start_A1_Mini.txt", "r", encoding="utf-8") as f:
    start_block = f.read()
with open("End_A1_Mini.txt", "r", encoding="utf-8") as f:
    end_block = f.read()
hs.markdown("# 3MF G-code Modifier")

uploaded_file = hs.file_upload("Upload your gcode.3mf file")
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
import os
import glob

base_dir = r"c:\Users\ankus\OneDrive\Desktop\MAXIS\maxis-core\maxis\memory"
files = glob.glob(os.path.join(base_dir, "*.py"))

for file_path in files:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace unsafe config.cloud checks
    new_content = content.replace("if config.cloud.database_url:", "if getattr(config, 'cloud', None) and config.cloud.database_url:")
    
    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Fixed {os.path.basename(file_path)}")

print("Done.")

import PyInstaller.__main__
import os
import sys
import shutil
import time
import subprocess

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Define the main script
main_script = 'main.py'

# Define additional data files to include
data_files = [
    ('images', 'images'),
    ('AutoSequenceRepo', 'AutoSequenceRepo'),
    ('search_regions.json', '.'),
    ('user_assets.json', '.'),
    ('requirements.txt', '.')
]

# Define hidden imports
hidden_imports = [
    'PIL._tkinter_finder',
    'skimage.metrics.structural_similarity',
    'utils.automation_helpers',
    'utils.debug_ui_widgets',
    'core.db',
    'ui_tabs.calendar_tab',
    'ui_tabs.importer_tab',
    'ui_tabs.job_card_manager_tab',
    'ui_tabs.job_indexer_tab',
    'ui_tabs.tag_manager_tab',
    'ui_tabs.batch_tasker_tab',
    'ui_tabs.job_card_instance',
    'ui_tabs.overview_tab',
    'ui_tabs.milwaukee_warranties_tab',
    'services.aden_controller',
    'services.aden_automation'
]

# Build the executable
# Format data files for Windows (using semicolons)
formatted_data_files = []
for src, dst in data_files:
    formatted_data_files.append(f"{src};{dst}")

# Check if the executable already exists and try to remove it
exe_path = os.path.join('dist', 'RepairsDashboard.exe')
if os.path.exists(exe_path):
    print(f"Found existing executable at {exe_path}")
    try:
        # Try to remove the file directly
        os.remove(exe_path)
        print("Successfully removed existing executable.")
    except PermissionError:
        print("Cannot remove executable - it may be in use.")
        # Try to terminate any running instances
        try:
            # Use taskkill to force terminate any running instances
            subprocess.run(['taskkill', '/F', '/IM', 'RepairsDashboard.exe'], 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("Terminated running executable instances.")
            # Wait a moment for the process to fully terminate
            time.sleep(2)
            # Try to remove the file again
            try:
                os.remove(exe_path)
                print("Successfully removed existing executable after termination.")
            except Exception as e:
                print(f"Still cannot remove executable: {e}")
                # As a last resort, try to rename the dist folder
                try:
                    if os.path.exists('dist_old'):
                        shutil.rmtree('dist_old')
                    os.rename('dist', 'dist_old')
                    print("Renamed dist folder to dist_old as a workaround.")
                except Exception as e:
                    print(f"Failed to rename dist folder: {e}")
        except Exception as e:
            print(f"Error terminating executable: {e}")

PyInstaller.__main__.run([
    main_script,
    '--name=RepairsDashboard',
    '--onefile',
    '--windowed',
    '--icon=images/job_card_loaded_cue.png',
    *[f'--add-data={data}' for data in formatted_data_files],
    *[f'--hidden-import={imp}' for imp in hidden_imports],
    '--clean',
    '--log-level=INFO'
])

print("Build completed successfully!")

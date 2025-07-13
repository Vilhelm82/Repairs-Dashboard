# Repairs Dashboard

## Building the Executable

This project can be converted to a standalone executable (.exe) file using PyInstaller. Follow these steps to build the executable:

1. **Run the Build Script**:
   - Double-click on the `build.bat` file in the project directory
   - This will automatically install PyInstaller if needed and build the executable

2. **Locate the Executable**:
   - After the build completes, the executable will be in the `dist` folder
   - The file will be named `RepairsDashboard.exe`

3. **Running the Application**:
   - Double-click on `RepairsDashboard.exe` to run the application
   - No Python installation is required to run the executable

## Debug Utility

A debug utility has been added to help with troubleshooting and development:

1. **Accessing the Debug Utility**:
   - Open the application
   - Go to the "Job Importer" tab
   - Click the "🔧 Debug Utility" button

2. **Features of the Debug Utility**:
   - Region debugging for UI automation
   - OCR testing
   - Automation sequence creation and testing
   - Screen region capture and analysis

## Notes

- The executable includes all necessary dependencies and resources
- Make sure to include the `images` and `AutoSequenceRepo` folders when distributing the application
- The database file (`jobs.db`) will be created in the same directory as the executable when the application is run
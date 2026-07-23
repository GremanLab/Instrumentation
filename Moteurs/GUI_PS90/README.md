# Graphic interface 

This project contains all files to manipulate the PS90(+) engine and an oscilloscope from Teledyne Lecroy.

You can manipulates those with graphic_interface.py (recommanded) or without those by creating your own file by being helped by
libraries used (in particular OWIS_PS90 and HDO4034A which are located in classes folder).

To use graphical interface there is a complete guide: /filename/

*This guide include:*
- Interface explanation
- Help for installation
- How to edit interface
- How to correct some common bugs

*If you want to create your own file, you must understand:*
- python imports
- OWIS_PS90 use a file called ps90.dll which allows you to communicate with ps90(+) engine
- HDO4034A is here to communicate with the oscilloscope (via ActiveDSO).
  There is another version (which could not work) which communicate via pyvisa
- you can use scan_classic.py to help you to make your code.


**Folder Structure**:
 
.
└── hydrophone_handling/
    ├── graphic_interface.py
    ├── Hydrophone Graphical Interface User Guide.docx
    ├── classes/
    │   ├── HDO4034A/
    │   │   └── HDO4034A.py
    │   ├── ps90/
    │   │   ├── ps90.dll
    │   │   ├── OWIS_PS90.py
    │   │   ├── LinearStageL84N.py
    │   │   └── RotaryStageDMT65.py
    │   ├── display_time.py
    │   └── path_import.py
    ├── images/
    │   ├── img_scan_length.png
    │   └── img_scan_point.png
    ├── matrix_csv/
    │   └── example.csv
    ├── out/
    ├── scan/
    │   ├── scan_by_interf.py
    │   ├── scan_for_matrix.py
    │   ├── scan_classic.py
    │   └── utils/
    │       ├── axe_def.py
    │       ├── break_timer.py
    │       ├── osc_scan_settings.py
    │       ├── scan_viewer.py      
    │       └── write_csv.py
    ├── USB Driver/
    │   └── CDM2123620_Setup.exe
    └── README.md


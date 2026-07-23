Content of a directory:

- readme.txt this file
- liesmich.txt german version of this file
..\SDK\zAdditional_software_interfaces\Python\Release
- ps90tool.py script file (32/64 bit) for demo program (e.g., WinPython, 32bit, 3.4.4.1 / Spyder 3.0.0)
..\SDK\zAdditional_software_interfaces\Python\Release Unicode
- ps90tool.py script file (32/64 bit, Unicode) for demo program (e.g., WinPython, 32bit, 3.4.4.1 / Spyder 3.0.0)
..\SDK\exe\x86\Release - demo program (32 bit), 12 batch files
- PS90.dll PS90-function library (version 2.0.0.2, 32 bit)
..\SDK\exe\x86\Release Unicode - demo program (32 bit, Unicode), 12 batch files
- PS90u.dll PS90-function library (version 2.0.0.2, 32 bit, Unicode)
..\SDK\exe\x64\Release - demo program (64 bit), 12 batch files
- PS90.dll PS90-function library (version 2.0.0.2, 64 bit)
..\SDK\exe\x64\Release Unicode - demo program (64 bit, Unicode), 12 batch files
- PS90u.dll PS90-function library (version 2.0.0.2, 64 bit, Unicode)

To use the functions in your application, make the following:
1. Copy the library "ps90.dll" or "ps90u.dll" into the working directory.

To use the demo application (32 bit), the following files are required:
- Visual C++ Runtime files
These files can be run as prerequisites during installation on a computer that does not have Visual C++ 2010 Express Edition (or higher) installed.
vcredist_x86.exe - Redistributable Package for Visual C++ (32 bit) 

To use the demo application (64 bit), the following files are required:
- Visual C++ Runtime files
These files can be run as prerequisites during installation on a computer that does not have Visual C++ 2010 Express Edition (or higher) installed.
vcredist_x64.exe - Redistributable Package for Visual C++ (64 bit) 

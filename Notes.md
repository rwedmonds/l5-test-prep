# Notes

RESTED extension in Firefox can also be used to send JSON formatted requests

To change the cursor color, press `cmd` + `shift` + `p` and type `settings.json` and choose `Preferences: Open User Settings (JSON)`. Paste in the following:

    "workbench.colorCustomizations": {
        "editorCursor.foreground": "#ffe600",
        "terminalCursor.foreground": "#ffe600"
    }

Ansible command to ping all hosts in inventory file (given the file is named **host.ini**):

`ansible -m ping all -i hosts.ini`

Sublime Collaboration
=====================

A real-time collaborative editing plugin for Sublime Text 2.

Instructions
------------
Please note that this plugin is in an early beta state, and much of the user interface and API will probably be rewritten at some point, so this is not representative of what the final product will be like.

### Install
Put everything in this repo into a folder named Collaboration under the /Data/Packages/ directory in your Sublime Text 2 folder.

### Usage
You can run commands via keyboard shortcuts or with the command prompt via Ctrl-Shift-P.

#### Commands
"Collaboration: Connect To Server": Connects to a Sublime Collaboration server. *ctrl+alt+c*  
"Collaboration: Disconnect From Server": Disconnect from server. *ctrl+alt+d*  
"Collaboration: Toggle Local Server": Toggles local server on and off. *ctrl+alt+s*  
"Collaboration: Open Document": Open a new or preexisting document on the server. *ctrl+alt+o*  
"Collaboration: Add Current Document": Uploads the currently open document to the server for collaborative editing. *ctrl+alt+a*

#### Example
If you're just testing this out, first toggle on your local server. Then connect to it and open a new document with the "Open Document" command. Currently you can't open the same document in the same Sublime Text process, so you'll need to connect to the server again from another computer to test out the collaborative aspects. It uses port 6633 if you need to make firewall rules. If all goes well, you should see changes in one buffer replicated on the other!

#### Bugs
If you find something that creates an error or doesn't seem to be working properly, please make an issue about it. There are bound to be errors that I don't catch, so any feedback would be appreciated!

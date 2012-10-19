Sublime Collaboration
=====================

A real-time collaborative editing plugin for Sublime Text 2.

Instructions
------------
Please note that this plugin is in an early beta state, and much of the user interface and API will probably be rewritten at some point, so this is not representative of what the final product will be like.

### Install
Put everything in this repo into a folder named Collaboration under the /Data/Packages/ directory in your Sublime Text 2 folder.

#### Commands
"Collaboration: Connect To Server": Connects to a Sublime Collaboration server. *Default Shortcut: ctrl+alt+c*  
"Collaboration: Disconnect From Server": Disconnect from server. *Default Shortcut: ctrl+alt+d*  
"Collaboration: Toggle Local Server": Toggles local server on and off. *Default Shortcut: ctrl+alt+s*  
"Collaboration: Open Document": Open a preexisting document on the server. *Default Shortcut: ctrl+alt+o*  
"Collaboration: Add Current Document": Uploads the currently open document to the server for collaborative editing. *Default Shortcut: ctrl+alt+a*

#### Example
If you're just testing this out, first toggle on your local server and connect to it. Then open up a new blank document and add it to the server with the "Add Current Document" command. Currently you can't open the same document in the same Sublime Text process, so you'll need to connect to the server again from another computer and open the document to test out the collaborative aspects. It uses port 6633 if you need to make firewall rules. If all goes well, you should see changes in one buffer replicated on the other.

#### Bugs
If you find something that creates an error or doesn't seem to be working properly, please make a GitHub issue about it. There are bound to be errors that I don't catch, so any feedback would be appreciated!

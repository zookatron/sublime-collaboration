Sublime Collaboration
=====================

A real-time collaborative editing plugin for Sublime Text 2.

Instructions
------------
Please note that this plugin is in a very early beta state, and most if not all of the user interface and API will probably be rewritten at some point, so this is not representative of what the final product will be like.

### Install
Put everything in this repo into a folder named Collaboration under the /Data/Packages/ directory in your Sublime Text 2 folder.

### Usage
Currently the only way to interact with the plugin is through keyboard shortcuts.

#### Keyboard Shortcuts
*ctrl+alt+c* Connect to a server
*ctrl+alt+d* Disconnect from server
*ctrl+alt+o* Open a document on the server
*ctrl+alt+s* Toggle local server on and off

#### Example
If you're just testing this out, first start a local server with ctrl+alt+s. Then connect to it with ctrl+alt+c. Then open a document with ctrl+alt+o. Currently you can't open the same document in the same Sublime Text process, so you'll need to connect to the server again on another computer to test out the collaborative aspects. It uses port 6633 if you need to make firewall rules.
- This is a python CLI app that syncs files to remote server via ftp. 

- The app will be called `hls`
- It will be installed via pip install, so we'll deploy it to PyPI. 
- we will support python 3.10 and above.
- we need a project set up (toml file etc).
- User can add mappings between any local folder and a remote folder.
    hls map <config-name> <remote-folder> [<local-folder>]
    - if <local-folder> is left out, the current folder is implied
    - <remote-folder> is the absolute destination path at the remote server
    - <config-name> is an existing remote server configuration added via:
        hls add <config-name> <type>
        - <config-name> is a valid JSON string
        - <type> is currently only `ftp`
        - the config will get saved in ~/.hls/configs.json
- You can set the default config to use so as not to include it in every command
    - hls set <config-name>
- Info commands:
    - hls h|elp
    - hls version
- Mappings are applied one-to-one, recursively to subfolders
    - Tool needs to identify and raise an error for conflicts when user tries to map a subfolder of a local folder already mapped
- Operations
    - hls u|pload   <local-file> [<remote-file-name>]
                    <local-folder>/ [<remote-folder-name>]
                    <local-folder>/*.js
                    *diff [<filter>]
    - hls d|ownload <remote-file> [<local-file-name>]
                    <remote-folder>/ [<local-folder-name>]
                    *diff [<filter>]
    - hls list l|ocal
               r|emote
               d|iff        # based on size & timestamp

# git-crate-registry #
`git-crate-registry` provides a template for hosting a Rust crate registry on a private git server,
 or local filesystem.

The template provides a Python 3 script, `add-crate.py` which packages a crate extracts, extacts 
the neccesary metadata and commits it to this repository. 

## how to deploy ##
  1. Clone this repository

  2. If you do not want to use git lfs, delete `.gitattributes` from the repository.

  3. Replace `PATH_TO_MASTER_RAW_FILES` in config.json with the URL prefix to download a file from
     the master branch of your repository. For example:

       * gitlab: `http://gitlab.com/USER/REPO/-/raw/master`
    
       * github: `https://raw.githubusercontent.com/USER/REPO/master`

  4. Commit these changes and push it to your git server
     
## adding a crate ##
Clone the repository to your local machine and run the following

```bash
./add-crate.py ../my-crate/
git push
```

Any compilation errors should be printed to the console. If not, ensure that `cargo metadata` and
 `cargo package` run without error. 

## using the registry ##
  1. Create or edit the `.cargo/config` file in either the folder of the project you're importing
     crates into, or your home folder (`~/.cargo/config` or `%USERPROFILE%\.cargo.config`)

  2. Add a registry entry pointing at the URL of your registry repository:
        ```toml
        [registries]
        my-registry = { index = "https://mygitserver.local/USERNAME/registry" }
        ``` 
  
  3. In `Cargo.toml`, declare imported crates by specifying their version and your custom registry name
        ```toml
        [dependencies]
        my_crate = { version = "0.1", registry = "my-registry"}
        ```

## local filesystem registy ##
This template can also be used as a local filesystem based crate registry. 

To use it in this mode:

   1. replace `PATH_TO_MASTER_RAW_FILES` with a `file://` URI pointing at the registry's location
      on the filesystem. e.g.
        ```json
        {
            "dl": "file:///Users/USERNAME/projects/registry/crates/{crate}/{crate}-{version}.crate"
        }
        ```

    2. Create a registry entry in `.cargo/config` with a `file://` URI pointing at the registry's
       location. e.g.
        ```toml
        [registries]
        my-registry = { index = "file:///Users/USERNAME/projects/registry" }
        ``` 

## debugging notes ##
If cargo is having issues resolving packages in your registry:

  1. Remove the cached registry from `~/.cargo/registry/index/`

  2. Set the variable `export CARGO_LOG=cargo::sources`

  3. Rerun your cargo command (e.g. `cargo build`)
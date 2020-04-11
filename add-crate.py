#! /usr/bin/env python3
#
# This script will publish a crate into this git based crate repository
import subprocess
import json
from pathlib import Path
import os
from os import path
import hashlib
import shutil
import sys

# Resolve the registry path as being the directory this script is in
REGISTRY_DIRECTORY = str(Path(__file__).resolve().parent)
CRATES_IO_UPSTREAM = "https://github.com/rust-lang/crates.io-index"

"""
do_cargo(crate_directory, arguments, allow_nonzero=False, shell_out=False))

Excecutes cargo in the given crate_directory, passing the arguments list to cargo.

Returns stdout as a bytestring if the command returns zero or allow_nonzero is True

Prints stdout if shell_out = True

Raises SystemError if the command fails (nonzero return code) and allow_nonzero=False

Raises FileNotFound if cargo_directory does not exist
"""
def do_cargo(crate_directory, arguments, allow_nonzero=False, shell_out=False):
    if not path.exists(crate_directory):
        raise FileNotFoundError(crate_directory)

    args = ["cargo"] + arguments

    out = None if shell_out else subprocess.PIPE

    p = subprocess.Popen(args, stdout=out, stderr=subprocess.PIPE, cwd=crate_directory, universal_newlines=True)

    # waittfor the 
    p.wait()

    if p.returncode == 0 or allow_nonzero:
        return p.stdout.read() if not shell_out else ""
    else:
        raise SystemError("failed to run {}, stderr: {}".format(" ".join(args), p.stderr.read()))



def do_git(arguments):
    arguments = ["git"] + arguments

    p = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=REGISTRY_DIRECTORY, universal_newlines=True)
    # wait
    p.wait()

    if p.returncode == 0:
        return p.stdout.read()
    else:
        raise SystemError("failed to run {}, stderr: {}".format(" ".join(args), p.stderr.read()))


"""
get_metadata(crate_directory)

Calculates the metadata json object for a crate

Returns a dict

Notes: 
  * the cksum field isn't populated
  * default_features for deps is set to true if not populated by `cargo metadata`
  * the registry of dependencies that aren't explicitly pined are defaulted to crates.io
"""
def get_metadata(crate_directory):
    cargo_metadata = json.loads(do_cargo(crate_directory, ["metadata", "--no-deps"]))["packages"][0]
    
    # populate missing fields and shuffle around:
    cargo_metadata["vers"] = cargo_metadata["version"]
    cargo_metadata["deps"] = cargo_metadata["dependencies"]
    cargo_metadata["yanked"] = False
    cargo_metadata["cksum"] = None

    # The list of fields to filter the metadata object down to
    TOP_LEVEL_FIELDS = [
        "name",
        "vers",
        "deps",
        "cksum",
        "features",
        "yanked",
        "links"
    ]

    # Fields to be retained in deps members
    DEPS_FIELDS = [
        "name",
        "req",
        "features",
        "optional",
        "default_features",
        "target",
        "kind",
        "registry",
        "package"
    ]

    # Filter object and deps down to mandatory fields
    for key in list(cargo_metadata.keys()):
        if key not in TOP_LEVEL_FIELDS:
            del cargo_metadata[key]

    # add any missing fields:
    for key in TOP_LEVEL_FIELDS:
        if key not in cargo_metadata.keys():
            cargo_metadata[key] = None

    # Filter and add missing fields to deps
    for dep in cargo_metadata["deps"]:
        for key in DEPS_FIELDS:
            if key not in dep:
                # fix default features bug if null
                dep[key] = None if key != "default_features" else True
        
        for key in list(dep.keys()):
            if  key not in DEPS_FIELDS:
                del dep[key]

        # We need to explicitly pin crates.io dependencies, otherwise
        # cargo assumes it'll be in this registry! :O 
        if dep["registry"] == None:
            dep["registry"] = CRATES_IO_UPSTREAM
    
    return cargo_metadata

"""
get_registry_directories(crate_name, version)

Calculates the directory names for the crate and metadata file

Returns tuple (download_dir, metadata_dir)
"""
def get_registry_directories(crate_name, version):
    download = REGISTRY_DIRECTORY + f"/crates/{crate_name}"

    if len(crate_name) in [1,2]:
        metadata = REGISTRY_DIRECTORY + "/{}".format(len(crate_name))
    elif len(crate_name) == 3:
        metadata = REGISTRY_DIRECTORY + "/{}/{}".format(3, crate_name[0])
    else:
        metadata = REGISTRY_DIRECTORY + "/{}/{}".format(crate_name[:2], crate_name[2:4])

    return (download, metadata)


"""
package_crate(crate_directory)

Packages the crate and returns the registry metadata

Returns (metadata_dict, crate_path)
"""
def package_crate(crate_directory):
    # Get the metadata and crate name/ver
    metadata = get_metadata(crate_directory)

    crate_name = metadata["name"]
    version = metadata["vers"]

    print(f"packaging {crate_name}-{version} in directory {crate_directory}")

    # Build the crate and test that it was successful
    do_cargo(crate_directory, ["package"], shell_out=True)

    crate_path = crate_directory + f"/target/package/{crate_name}-{version}.crate"

    if not path.exists(crate_path):
        raise FileNotFoundError(f"{crate_path} missing after packaging")

    print(f"success, crate at {crate_path}")

    # calculate the checksum
    with open(crate_path, "rb") as f:
        sha256 = hashlib.sha256()
        sha256.update(f.read())
        metadata['cksum'] = sha256.hexdigest()

    return (metadata, crate_path)


"""
update_registry(metadata, crate_path)

Adds and commits a new crate to the registry repository
""" 
def update_registry(metadata, crate_path):
    # Create the directories for the metadata and crate if they don't exist
    crate_folder, metadata_folder = get_registry_directories(metadata["name"], metadata["vers"])

    # Create the directories, ignore if already exist
    try:
        os.makedirs(metadata_folder)
    except FileExistsError:
        pass

    try:
        os.makedirs(crate_folder)
    except FileExistsError:
        pass

    print(f"created registry directories {metadata_folder}, {crate_folder}")

    metadata_file = f"{metadata_folder}/" + metadata["name"]

    # Try update the metadata file
    version_lines = []

    try:
        with open(metadata_file, "r") as f:
            print("opened metadata file {} to remove existing entry for {}-{}".format(
                metadata_file, metadata["name"], metadata["vers"]))
            # filter exisiting entry for this version
            for line in f.readlines():
                mline = json.loads(line)
                if not mline["vers"] == metadata["vers"]:
                    version_lines.append(line)

    except FileNotFoundError:
        # Ignore file not found, we'll create it anyway
        pass
    
    # Add this version and write it to disk
    version_lines.append(json.dumps(metadata))
    with open(metadata_file, "w") as f:
        f.write("\n".join(version_lines))

    print(f"wrote new version line to metadata file {metadata_file}")
    
    # Copy the crate
    registry_crate_file = "{}/{}-{}.crate".format(crate_folder, metadata["name"], metadata["vers"])
    shutil.copy(crate_path, registry_crate_file)
    print(f"wrote crate to directory {registry_crate_file}")


    # Commit changes
    do_git(["add", registry_crate_file, metadata_file])
    do_git(["commit", "-m", "updated crate {} to version {}".format(metadata["name"], metadata["vers"])])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("{} crate_path".format(sys.argv[0]))
        exit(1)
    
    metadata, crate_file = package_crate(sys.argv[1])
    update_registry(metadata, crate_file)
    print("completed, make sure to run \"git push\" to push your changes")



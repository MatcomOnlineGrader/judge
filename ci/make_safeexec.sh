#!/bin/bash
# Clone and install the safeexec binary, with some patches
# Requires: git, cmake, make, g++

info(){
	echo "[*]" $*
}

warn(){
	echo -e "\n[=====================]\n"
	echo "[!]" $*
}

build() {
	# First go to a temp folder
	info "Changing to a temprorary directory"
	ODIR=$PWD
	TDIR=$(mktemp -d)
	cp ci/*.patch $TDIR
	cd $TDIR

	# Now clone and apply the patches
	info "Cloning safeexec..."
	git clone https://github.com/ochko/safeexec || { warn "Error cloning repository, aborting"; exit 1; }
	cp *.patch safeexec
	cd safeexec

	# Run cmake
	info "Running cmake..."
	cmake . || { warn "Could not execute cmake, aborting"; exit 1; }

	# Apply patches
	echo *.patch
	for p in *.patch; do
		info "Applying patch: $p"
		patch < $p || { warn "Could not apply patch, aborting"; exit 1; }
	done

	# Install system-wide
	info "Installing..."
	make install || { warn "Could not run `make install`, aborting"; exit 1; }

	# Remove unnecesary stuff in this directory
	info "Removing unnecesary files..."
	cd $ODIR
	rm -rf $TDIR

	info "Everything OK"
}

build $@

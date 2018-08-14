# -*- encoding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2016-2018 Tobias Koch <tobias.koch@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import os
import re
import stat
import hashlib
import functools
import tempfile

import org.boltlinux.package.libarchive as libarchive

from tempfile import TemporaryDirectory, NamedTemporaryFile
from org.boltlinux.package.libarchive import ArchiveFileReader, \
        ArchiveFileWriter, ArchiveEntry
from org.boltlinux.error import BoltSyntaxError
from org.boltlinux.package.xpkg import BaseXpkg
from org.boltlinux.package.metadata import PackageMetaData

class RepoIndexer:

    def __init__(self, repo_dir, force_full=False):
        self._force_full = force_full
        self._repo_dir   = repo_dir
    #end function

    def update_package_index(self):
        index = {} if self._force_full else self.load_package_index()

        for meta_data in self.scan(index=index):
            name    = meta_data["Package"]
            version = meta_data["Version"]

            index\
                .setdefault(name, {})\
                .setdefault(version, meta_data)
        #end for

        self.prune_package_index(index)
        self.store_package_index(index)

        self.make_hash_links()
    #end function

    def load_package_index(self):
        packages_file = os.path.join(self._repo_dir, "Packages.gz")

        if not os.path.exists(packages_file):
            return {}

        buf = ""

        with ArchiveFileReader(packages_file, raw=True) as archive:
            for entry in archive:
                buf = archive\
                    .read_data()\
                    .decode("utf-8")
        #end with

        index = {}

        for entry in re.split(r"\n\n+", buf, flags=re.MULTILINE):
            meta_data = PackageMetaData(entry)

            try:
                name    = meta_data["Package"]
                version = meta_data["Version"]
            except KeyError:
                continue

            index.setdefault(name, {})[version] = meta_data
        #end for

        return index
    #end function

    def prune_package_index(self, index):
        for name in list(index.keys()):
            for version, meta_data in list(index[name].items()):
                abspath  = os.path.join(self._repo_dir, meta_data["Filename"])

                if not os.path.exists(abspath):
                    del index[name][version]
            #end for
        #end for
    #end function

    def store_package_index(self, index):
        packages_file = os.path.join(self._repo_dir, "Packages.gz")

        meta_data_list = []

        for name in sorted(index.keys()):
            for version in sorted(index[name].keys(), key=functools.cmp_to_key(
                    BaseXpkg.compare_versions)):
                meta_data_list.append(index[name][version])
            #end for
        #end for

        if not meta_data_list:
            return

        output = "\n".join([entry.as_string() for entry in meta_data_list])
        output = output.encode("utf-8")

        with NamedTemporaryFile(dir=self._repo_dir, delete=False) as tempfile:
            pass

        try:
            options = [("gzip", "timestamp", None)]

            with ArchiveFileWriter(tempfile.name, libarchive.FORMAT_RAW,
                    libarchive.COMPRESSION_GZIP, options=options) as archive:

                with ArchiveEntry() as archive_entry:
                    archive_entry.filetype = stat.S_IFREG
                    archive.write_entry(archive_entry)
                    archive.write_data(output)
                #end with
            #end with

            os.chmod(tempfile.name,
                stat.S_IRUSR |
                stat.S_IWUSR |
                stat.S_IRGRP |
                stat.S_IROTH
            )

            os.rename(tempfile.name, packages_file)
        finally:
            if os.path.exists(tempfile.name):
                os.unlink(tempfile.name)
        #end try
    #end function

    def make_hash_links(self):
        packages_file = os.path.join(self._repo_dir, "Packages.gz")

        sha256sum = self._compute_sha256_sum(packages_file)
        sha256dir = os.path.join(self._repo_dir, "by-hash", "SHA256")
        linkname  = os.path.join(sha256dir, sha256sum)

        if os.path.exists(linkname):
            return

        if not os.path.isdir(sha256dir):
            os.makedirs(sha256dir)
        else:
            for entry in os.scandir(path=sha256dir):
                if entry.is_symlink():
                    os.unlink(os.path.join(sha256dir, entry.name))
            #end for
        #end if

        os.symlink("../../Packages.gz", linkname)
    #end function

    def scan(self, index=None):
        if index is None:
            index = {}

        for path, dirs, files in os.walk(self._repo_dir, followlinks=True):
            for filename in files:
                if not filename.endswith(".bolt"):
                    continue

                try:
                    name, version, arch = filename[:-5].rsplit("_")
                except ValueError:
                    continue

                entry = index.get(name, {}).get(version, None)

                if entry is not None:
                    continue

                abs_path = os.path.join(path, filename)

                try:
                    control_data = self.extract_control_data(abs_path)
                except BoltSyntaxError as e:
                    continue

                yield control_data
            #end for
        #end for
    #end function

    def extract_control_data(self, filename):
        meta_data = None

        with TemporaryDirectory() as tmpdir:
            with ArchiveFileReader(filename) as archive:
                for entry in archive:
                    if not entry.pathname.startswith("control.tar."):
                        continue

                    data_file = os.path.join(tmpdir, entry.pathname)

                    with open(data_file, "wb+") as outfile:
                        while True:
                            buf = archive.read_data(4096)
                            if not buf:
                                break
                            outfile.write(buf)
                        #end while
                    #end with

                    pool_path = re.sub(r"^" + re.escape(self._repo_dir) + r"/*",
                            "", filename)

                    meta_data = PackageMetaData(
                        self._extract_control_data(data_file))

                    meta_data["Filename"] = pool_path

                    break
                #end for
            #end with
        #end with

        meta_data["SHA256"] = self._compute_sha256_sum(filename)
        meta_data[ "Size" ] = os.path.getsize(filename)

        return meta_data
    #end function

    # PRIVATE

    def _extract_control_data(self, filename):
        with ArchiveFileReader(filename) as archive:
            for entry in archive:
                if not entry.pathname == "control":
                    continue

                meta_data = archive\
                    .read_data()\
                    .decode("utf-8")

                meta_data = \
                    re.sub(r"^\s+.*?$\n?", "", meta_data, flags=re.MULTILINE)

                return meta_data.strip()
            #end for
        #end with
    #end function

    def _compute_sha256_sum(self, filename):
        sha256 = hashlib.sha256()

        with open(filename, "rb") as f:
            while True:
                buf = f.read(4096)

                if not buf:
                    break

                sha256.update(buf)
            #end while
        #end with

        return sha256.hexdigest()
    #end function

#end class

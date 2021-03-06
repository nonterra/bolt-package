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
import logging

from org.boltlinux.package.appconfig import AppConfig
from org.boltlinux.package.xpkg import BaseXpkg
from org.boltlinux.repository.flaskinit import app, db
from org.boltlinux.repository.models import UpstreamSource
from org.boltlinux.repository.debiansourceslist import DebianSourcesList
from org.boltlinux.repository.repotask import RepoTask
from org.boltlinux.error import RepositoryError

class DebianSources(RepoTask):

    def __init__(self, config, verbose=True):
        super().__init__("debian-sources")

        self._release = config.get("release", {}).get("upstream", "stable")

        config = config.get("upstream", {})

        self._verbose    = verbose
        self._components = config.get("components", ["main"])

        self._mirror = config.get(
            "mirror", "http://ftp.debian.org/debian/"
        )
        self._security = config.get(
            "security", "http://security.debian.org/debian-security/"
        )

        self._cache_dir  = \
            config.get("cache-dir",
                os.path.realpath(
                    os.path.join(
                        AppConfig.get_config_folder(),
                        "cache", "upstream", self._release
                    )
                )
            )

        self.log = logging.getLogger("org.boltlinux.repository")
    #end function

    def run_task(self):
        self.refresh()
        self.update_db()
    #end function

    def refresh(self):
        mirror_list = [
            (self._mirror, False),
            (self._security, True)
        ]

        for component in self._components:
            for mirror, is_security in mirror_list:
                if self.is_stopped():
                    break

                sources_list = DebianSourcesList(
                    release     = self._release,
                    component   = component,
                    mirror      = mirror,
                    cache_dir   = self._cache_dir,
                    is_security = is_security
                )

                try:
                    if not sources_list.is_up2date():
                        if self._verbose:
                            msg = "Refreshing Debian source Packages list "\
                                    "for component '%s%s'."
                            self.log.info(msg % (component,
                                " (security)" if is_security else ""))
                        #end if

                        sources_list.refresh()
                except RepositoryError as e:
                    msg = "Error updating Debian sources for" \
                            " component '%s': %s"
                    self.log.error(msg % (component, str(e)))
                #end try
            #end for
        #end for
    #end function

    def update_db(self):
        mirror_list = [
            (self._mirror, False),
            (self._security, True)
        ]

        with app.app_context():
            stored_pkg_index = \
                dict([(obj.name, obj) for obj in UpstreamSource.query.all()])

            for component in self._components:
                for mirror, is_security in mirror_list:
                    if self.is_stopped():
                        break

                    if self._verbose:
                        self.log.info(
                            "Updating Debian sources DB entries for component "
                            "'{}{}'.".format(
                                component, " (security)" if is_security else ""
                            )
                        )
                    #end if

                    sources_list = DebianSourcesList(
                        release     = self._release,
                        component   = component,
                        mirror      = mirror,
                        cache_dir   = self._cache_dir,
                        is_security = is_security
                    )

                    self._parse_revisions(
                        component,
                        sources_list,
                        stored_pkg_index
                    )
                #end if
            #end for

            db.session.commit()
        #end with
    #end function

    # PRIVATE

    def _parse_revisions(self, component, sources_list, stored_pkg_index):
        for pkg_info in sources_list:
            if self.is_stopped():
                break

            pkg_name    = pkg_info["Package"]
            pkg_version = pkg_info["Version"]

            if pkg_name not in stored_pkg_index:
                source_pkg = UpstreamSource(
                    name      = pkg_name,
                    version   = pkg_version,
                    component = component
                )
                db.session.add(source_pkg)
                stored_pkg_index[pkg_name] = source_pkg
            else:
                source_pkg = stored_pkg_index[pkg_name]

                old_version = source_pkg.version
                new_version = pkg_info["Version"]

                if BaseXpkg.compare_versions(
                        new_version, old_version) > 0:
                    source_pkg.version = new_version
            #end if
        #end for
    #end function

#end class

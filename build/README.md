# Native tmux and reptyr packages

`packages/tmux-3.5a-x86_64-2_andrebrait.txz` and `packages/reptyr-0.10.0-x86_64-2_andrebrait.txz` are built from source by
`.github/workflows/native-ttm.yml`, replacing the prebuilt `_slack15.x` packages of unknown provenance. The older package
files stay in `packages/` because already-installed plugin versions may still fetch them.

The approach is shared with [andrebrait/NUT-unRAID](https://github.com/andrebrait/NUT-unRAID) and reuses the
[NerdTools](https://github.com/andrebrait/unRAID-NerdTools) build infrastructure at the commit pinned in the workflow:
the exact Unraid 7.3.4 root (SHA256-pinned) plus the SHA256-pinned development packages in `locks/toolchain.json`
(additive; Unraid's own runtime libraries are never replaced), compiled in a Bubblewrap sandbox with no network.

| Package | Version | Recipe | Source |
| --- | --- | --- | --- |
| tmux | 3.5a | `recipes/tmux`: Slackware `source/ap/tmux` at [`5d952c9`](https://git.slackware.nl/current/plain/source/ap/tmux/tmux.SlackBuild?id=5d952c9da3aefac7b34a2a1168554d17e80ec0be) (Patrick J. Volkerding; script, `doinst.sh`, `slack-desc`, `tmux.conf` byte-identical to the replaced package except for the changes noted in the script header) | upstream release tarball, SHA256 in `ttm.json` |
| reptyr | 0.10.0 | `recipes/reptyr`: SlackBuilds.org `system/reptyr` at [`ec1d154`](https://github.com/SlackBuildsOrg/slackbuilds/tree/ec1d154d9e9a5ccfad04d0168563d682feb5125e/system/reptyr) (B. Watson, WTFPL) | GitHub tag tarball; MD5 matches the SlackBuilds.org `.info` |

Each run verifies the packages on the exact Unraid **7.3.4** and **7.4.0** roots: `upgradepkg --install-new`, the ELF
dependency closure of every binary (`ld.so --list`), `tmux -V`, `reptyr -v`, and a detached tmux session started and listed
as root. A dispatch with `publish` commits the verified packages and `.md5` files to `packages/` (only possible from the
default branch; the first set was committed from the run artifact).

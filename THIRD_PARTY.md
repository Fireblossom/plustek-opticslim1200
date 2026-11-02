# Third-party components

The original integration code in this repository is licensed under GPL-3.0-or-later. It is an independent compatibility project, not an official Plustek driver.

## SANE

- Upstream: https://gitlab.com/sane-project/backends
- Version used for the Windows build: 1.4.0.
- License: GPL-2.0-or-later, with the linking exception described in the upstream source headers.
- `windows/compat.patch` contains modifications to upstream SANE files. Their original notices and licensing continue to apply. Obtain the complete upstream source from the pinned URL in `windows/build-cygwin.sh` / `README.md` and apply the patch.
- Relevant original source credits include Sergey Vlasov and Henning Geinitz for gt68xx, and the SANE project contributors for the common backend, test backend and SCSI support.

## Runtime dependencies

The Mac setup uses the native Homebrew distributions of SANE and Python. The Windows build uses Cygwin and libusb. Python mDNS support is provided by the `zeroconf` package and its dependencies. These are separate third-party projects; installing or redistributing them remains subject to their own notices and licenses. Their binaries are not included in the public source repository.

## Protocol references

- SANE gt68xx documentation: https://sane-project.gitlab.io/website/man/sane-gt68xx.5.html
- AirSane, a separate mature implementation of the SANE-to-AirScan approach: https://github.com/SimulPiscator/AirSane
- Windows eSCL support: https://support.microsoft.com/en-us/servicing/os/windows-10/2022/06/june-28-2022-kb5014666-os-builds-19042-1806-19043-1806-and-19044-1806-preview

The eSCL bridge was implemented for this project. AirSane was consulted for protocol interoperability details; its binaries and source tree are not bundled here.

## Scanner firmware

The manufacturer firmware is not original project code and is not distributed in this repository. Users must supply firmware from their own OpticSlim 1200 driver. Files with the same name from other scanner models are not interchangeable.

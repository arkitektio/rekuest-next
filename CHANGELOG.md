# CHANGELOG


## v0.5.8 (2025-05-04)


## v0.5.7 (2025-05-04)

### Bug Fixes

- Add readme and homepage information to pyproject.toml
  ([`84af7e4`](https://github.com/arkitektio/rekuest-next/commit/84af7e48d727d73bd7dbb6cc7776198347623c47))

- Update project name in README and version in uv.lock; add coverage workflow
  ([`c0c2fd9`](https://github.com/arkitektio/rekuest-next/commit/c0c2fd9c154f0243daab1f97e85072b2b85bdb1a))


## v0.5.6 (2025-05-04)

### Bug Fixes

- Update installation command in README to use rekuest-next
  ([`4f0c533`](https://github.com/arkitektio/rekuest-next/commit/4f0c5336295f297ca9646dd9ceeb62d06ae61b58))


## v0.5.5 (2025-05-04)

### Bug Fixes

- Add missing environment variable for semantic-release step
  ([`5f4608c`](https://github.com/arkitektio/rekuest-next/commit/5f4608ce33408566f0212f377d6673de85165bf0))

- Improve release workflow by updating step names and removing unused tokens
  ([`54991fd`](https://github.com/arkitektio/rekuest-next/commit/54991fd8e6d3c391bff4344e0e10d2b65b45cab9))

- Remove outdated distribution files for rekuest_next
  ([`440eade`](https://github.com/arkitektio/rekuest-next/commit/440eade234e857ac55aed2731eef1d254999fc59))

- Update semantic-release command and bump rekuest-next version to 0.5.4
  ([`575c63c`](https://github.com/arkitektio/rekuest-next/commit/575c63cfe25bd2734689d976e06680fe9bdafddf))


## v0.5.4 (2025-05-04)

### Bug Fixes

- Update semantic-release version step and bump rekuest-next version to 0.5.3
  ([`4505c6a`](https://github.com/arkitektio/rekuest-next/commit/4505c6a94eee4f5f437ec7b5ea2b94dcab521693))


## v0.5.3 (2025-05-04)

### Bug Fixes

- Update semantic-release command and reset version in pyproject.toml
  ([`db8a083`](https://github.com/arkitektio/rekuest-next/commit/db8a083e3bc7b4a6817759904c49dd7bf394c87f))


## v0.5.2 (2025-05-04)

### Bug Fixes

- Bump version of rekuest-next from 0.4.1 to 0.4.2
  ([`e7cb439`](https://github.com/arkitektio/rekuest-next/commit/e7cb439f0d300814e79abfd5fd00c2440eb2886d))


## v0.5.1 (2025-05-04)

### Bug Fixes

- Update versioning configuration in pyproject.toml
  ([`26b2996`](https://github.com/arkitektio/rekuest-next/commit/26b2996243276a98851937d08ce7da404d76adfb))


## v0.5.0 (2025-05-04)

### Bug Fixes

- Change version source from tag to file in semantic release configuration
  ([`b777e55`](https://github.com/arkitektio/rekuest-next/commit/b777e552dc5c47bcaa727843692fae1b1347a314))

- Remove --locked option from uv sync command in CI workflow
  ([`65d8631`](https://github.com/arkitektio/rekuest-next/commit/65d86312b2b70c279ff6a62a2eb6d0277166ea29))

- Remove --locked option from uv sync command in release workflow
  ([`e3e1642`](https://github.com/arkitektio/rekuest-next/commit/e3e1642203420eedbfb565d161a57f4133f9577f))

### Features

- Add optional dependency for annotated-types and update dev dependencies
  ([`05955bf`](https://github.com/arkitektio/rekuest-next/commit/05955bf55cdf1b17a45572c65c2428269c215d5f))

- Update GitHub Actions workflows to use setup-uv@v6 and add deploy workflow for GitHub Pages
  ([`8c5538b`](https://github.com/arkitektio/rekuest-next/commit/8c5538bbf7f028dd47462a567b3692db32cd1541))


## v0.4.3 (2025-05-04)

### Bug Fixes

- Add version variable for semantic release and define __version__ in __init__.py
  ([`3633438`](https://github.com/arkitektio/rekuest-next/commit/3633438295f989d98e9aec7e54de3200c0e96037))

- Ensure full Git history is available by setting fetch-depth in checkout step
  ([`d533b60`](https://github.com/arkitektio/rekuest-next/commit/d533b60ea15d633ba5ca841ae8b27aadc4783e0d))

- Update pyproject.toml to use dynamic versioning and specify version path
  ([`043f91e`](https://github.com/arkitektio/rekuest-next/commit/043f91e54da6e31c5116b95ac290ad09e9495d8d))

- Update semantic-release command to use 'version' instead of 'publish'
  ([`a642f82`](https://github.com/arkitektio/rekuest-next/commit/a642f82bd22ffe09f4c3dcce9901b5190b4191d9))


## v0.4.2 (2025-05-04)

### Bug Fixes

- Correct typo in docstring for nested structure expansion test
  ([`a5fbc72`](https://github.com/arkitektio/rekuest-next/commit/a5fbc729a1cb33e1181c0124c2c3bf5c778c2849))


## v0.4.1 (2025-05-04)

### Bug Fixes

- Correct typo in docstring for nested structure expansion test
  ([`f57fda3`](https://github.com/arkitektio/rekuest-next/commit/f57fda343ab5a23e3a76cb163e5c2301cce07f9b))


## v0.4.0 (2025-05-04)

### Bug Fixes

- Consolidate uv installation and Python version setup in release workflow
  ([`8715ead`](https://github.com/arkitektio/rekuest-next/commit/8715ead8ca66f2cd35d158ee69ecbab47736137f))

- Ensure Python version is set correctly in release workflow
  ([`e5b1a05`](https://github.com/arkitektio/rekuest-next/commit/e5b1a05464faecedc6000cb145e738374838344f))

- Remove Python 3.13 from CI testing matrix
  ([`eaf6b1a`](https://github.com/arkitektio/rekuest-next/commit/eaf6b1acfafd43382e672dd13f021d2721bb3634))

### Chores

- Update version to 0.2.72 and refactor agent extension methods
  ([`869d625`](https://github.com/arkitektio/rekuest-next/commit/869d62586682973a928c7248a69e5234906ffb50))

### Features

- Add CI workflow for testing across multiple Python versions and platforms
  ([`66ac1e7`](https://github.com/arkitektio/rekuest-next/commit/66ac1e716858002017045937542bc5ec6b562dc0))

- Add GitHub Actions workflow for pull request testing
  ([`bb9a93f`](https://github.com/arkitektio/rekuest-next/commit/bb9a93f58b8276bce83682aeb231dce9b4c04bde))

- Created a new GitHub Actions workflow (`pull.yaml`) to automate testing on pull requests targeting
  the main branch. - The workflow installs the necessary dependencies and runs tests using `pytest`.

feat: Implement GraphQL mutations for shelving and unshelving

- Added GraphQL mutations `shelve` and `unshelve` to manage memory drawer operations. - The `shelve`
  mutation accepts input to shelve items, while the `unshelve` mutation allows for unshelving.

feat: Introduce Local Structure Hook for memory management

- Developed `MemoryStructureHook` to register classes as memory structures. - Implemented utility
  functions for identifier conversion and error handling.

test: Add serialization tests for in-memory structures

- Created tests in `test_serialization_local.py` to validate serialization logic for in-memory
  structures. - Ensured that inputs can be shrunk and outputs are correctly shelved.

- Add WrappedThreadedBackgroundTask for synchronous background task execution and update version to
  0.2.73
  ([`7aea977`](https://github.com/arkitektio/rekuest-next/commit/7aea97773bca9d5472863ea4abbbb986b6a53c20))

- Update Python version matrix to include 3.13 for CI testing
  ([`c869d20`](https://github.com/arkitektio/rekuest-next/commit/c869d204225bf1d350a9f3e1c879844c5e7c0599))

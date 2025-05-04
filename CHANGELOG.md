# CHANGELOG


## v0.4.2 (2025-05-04)

### Bug Fixes

- Correct typo in docstring for nested structure expansion test
  ([`a5fbc72`](https://github.com/jhnnsrs/rekuest-next/commit/a5fbc729a1cb33e1181c0124c2c3bf5c778c2849))


## v0.4.1 (2025-05-04)

### Bug Fixes

- Correct typo in docstring for nested structure expansion test
  ([`f57fda3`](https://github.com/jhnnsrs/rekuest-next/commit/f57fda343ab5a23e3a76cb163e5c2301cce07f9b))


## v0.4.0 (2025-05-04)

### Bug Fixes

- Consolidate uv installation and Python version setup in release workflow
  ([`8715ead`](https://github.com/jhnnsrs/rekuest-next/commit/8715ead8ca66f2cd35d158ee69ecbab47736137f))

- Ensure Python version is set correctly in release workflow
  ([`e5b1a05`](https://github.com/jhnnsrs/rekuest-next/commit/e5b1a05464faecedc6000cb145e738374838344f))

- Remove Python 3.13 from CI testing matrix
  ([`eaf6b1a`](https://github.com/jhnnsrs/rekuest-next/commit/eaf6b1acfafd43382e672dd13f021d2721bb3634))

### Chores

- Update version to 0.2.72 and refactor agent extension methods
  ([`869d625`](https://github.com/jhnnsrs/rekuest-next/commit/869d62586682973a928c7248a69e5234906ffb50))

### Features

- Add CI workflow for testing across multiple Python versions and platforms
  ([`66ac1e7`](https://github.com/jhnnsrs/rekuest-next/commit/66ac1e716858002017045937542bc5ec6b562dc0))

- Add GitHub Actions workflow for pull request testing
  ([`bb9a93f`](https://github.com/jhnnsrs/rekuest-next/commit/bb9a93f58b8276bce83682aeb231dce9b4c04bde))

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
  ([`7aea977`](https://github.com/jhnnsrs/rekuest-next/commit/7aea97773bca9d5472863ea4abbbb986b6a53c20))

- Update Python version matrix to include 3.13 for CI testing
  ([`c869d20`](https://github.com/jhnnsrs/rekuest-next/commit/c869d204225bf1d350a9f3e1c879844c5e7c0599))

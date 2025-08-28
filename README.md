# Pixi Build Testsuite

This repo contains the testsuite that is used by both [Pixi] CI and [pixi-build-backends] CI to verify that they work properly in combination.


## Local development

First make sure that you have both the [Pixi] and [pixi-build-backends] repositories checked out locally.

Then, create a `.env` file at the repository root with the paths to your checked out repositories filled in.

```shell
PIXI_REPO="/path/to/pixi-repository"
BUILD_BACKENDS_REPO="/path/to/pixi-build-backends-repository"

PIXI_BIN_DIR="${PIXI_REPO}/target/pixi/release"
BUILD_BACKENDS_BIN_DIR="${BUILD_BACKENDS_REPO}/target/pixi/release"
```

You can build the executables by running the following Pixi task.
It will also make sure that your repositories are up-to-date:

```shell
pixi run build-repos
```

Finally, you can run the fast subset of the tests with the following task.
Also, check out the other Pixi tasks to run more tests on your local machine:

```shell
pixi run test
```

## Testing PR combinations in CI

To test a combination of PRs from this testsuite with PRs from [Pixi] or [pixi-build-backends]:

1. Create a `.env.ci` file with PR numbers:
   ```shell
   # Test with specific PR from pixi repository
   PIXI_PR_NUMBER="123"
   
   # Test with specific PR from pixi-build-backends repository  
   BUILD_BACKENDS_PR_NUMBER="456"
   ```
2. The CI will download artifacts from these PRs instead of main branch
3. **Important**: Remove `.env.ci` before merging to main (CI will prevent merge if present)

This allows you to test how your testsuite changes work with specific PRs from the other repositories.


[Pixi]: https://github.com/prefix-dev/pixi
[pixi-build-backends]: https://github.com/prefix-dev/pixi-build-backends

# Java probe harness — processor-level red→green when `./gradlew test` cannot run

## The blocker

`./gradlew test` **cannot discover tests** in `trustt-platform-accounting` (and any repo on
the same `accounting.dependency.gradle.plugin` dependency set):

```
JUnitException: TestEngine with ID 'junit-jupiter' failed to discover tests
Caused by: NoSuchMethodError: ReflectionUtils.returnsVoid(java.lang.reflect.Method)
```

`infra-transaction-hdfc` pins `junit-jupiter-engine:5.7.1` + `junit-platform-runner:1.7.1`
while the Spring Boot 3.5.6 BOM resolves `junit-platform-commons` to 1.12.x.

- Discovery fails on **every** class (it dies on `AbstractIntegerBaseEntityTest`), so
  `--tests <mine>` does **not** dodge it. A `--tests` run that "fails" tells you nothing.
- It cannot simply be pinned **up**: **527 of 547** accounting tests use
  `@RunWith(JUnitPlatform.class)`, a runner removed in junit-platform 1.11.
- Versions come from the external gradle plugin, not `build.gradle` — realigning is a
  cross-repo decision. Do not slip it into a bug fix.

## Use a probe instead

```bash
bash scripts/testing/javaprobe/run-probe.sh <repo> <probe.java>
bash scripts/testing/javaprobe/run-probe.sh trustt-platform-accounting \
     scripts/testing/foreclosure/probes/ShgSweepProbe.java
```

Real production classes, real Gradle **test runtime classpath**, a `main()` that exits
non-zero on failure — no JUnit, so no discovery. Classpath is cached per repo
(`--refresh` after a dependency change). Seconds per run, which is what a same-day fix needs.

Stub a DAO by subclassing it and overriding the finders; inject with reflection on the
`@Autowired` field. Precedent: `ShgSweepProbe.java` (registry case
`foreclosure.shg_sweep_terminal_guard`, TDPQA-72).

## Beware the stale-build trap

Gradle reports `compileJava UP-TO-DATE` after a `cp`-based file restore and the probe then
runs the **old** classes — a red→green that proves nothing. Change files with git
(`stash` / `checkout`) and let the runner call `compileJava`, or pass `--rerun-tasks`.
Always print the observed value in the probe so a stale run is visible.

Related: [[feedback_ship_test_autonomy_change_map]]


## KG cache: a miss is a 93s rebuild, a hit is 2s

`kg-switch.sh` restores from `cursor-bundle/kg/data/cache/<key>.db` when the composite key
matches. Measured: **hit 2.4s, miss 93s**. The key covers every repo's branch+HEAD+dirty
diff *and the KG's own sources* — so editing anything under `cursor-bundle/kg/**`
invalidates it and the next switch is a full rebuild.

That is correct behaviour, but it means `kg_enhance` (which guards the inner switch with
40s) cannot succeed while a rebuild is pending; it returns `kg_switch_rc: 124` with a named
error rather than hanging. If KG tools feel slow right after you edited KG source, run
`bash scripts/bin/kg-switch.sh` once to pay the rebuild, then everything is ~2s again.

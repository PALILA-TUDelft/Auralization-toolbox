# Prebuilt ART binaries

`win-x64-py313/` holds the compiled ART module and the ITA libraries it needs, so
a plain `git clone` is enough to run the propagation code. Nothing has to be
downloaded or compiled. The toolbox finds this folder by itself.

**Only for Windows x64 with Python 3.13.** The module
`_art_core.cp313-win_amd64.pyd` loads on that interpreter and on no other. Any
other Python version, macOS and Linux build ART from source: see
[BUILD.md](../BUILD.md).

The Microsoft Visual C++ Redistributable (x64, 14.29 or newer) must be installed;
Python usually installs it.

## Where these files come from

They were built with `tools/build_art.ps1` from this repository (the ITA
submodule at `ITAGeometricalAcoustics_v2025a-1-g59dbdda`, dependencies pinned by
`patches/ita/dependency-lock.json`), with Visual Studio 2019 Build Tools (MSVC
v142, 19.29), CMake 3.27.9, Python 3.13.2 and nanobind 2.13.0, in Release.
The same build, run from a fresh clone on a clean GitHub Actions machine, is the
[Fresh-clone build workflow](../.github/workflows/fresh-clone-build.yml).

| File | Size (bytes) | SHA-256 |
|---|---:|---|
| `_art_core.cp313-win_amd64.pyd` | 113,152 | `9ad334d08ff36fc2c943dff7d58eca62264eef20019d83f1a8553607f3e19c62` |
| `assimp-vc142-mt.dll` | 5,517,824 | `0f4119c74c95755039c361033ef39c21f1a79f7cb89fdc5f3accf4938469494a` |
| `DAFF.dll` | 83,456 | `317097f4f1c742c6cc13b6a21c41341d4ccb49f5a6acbd308e0fbc2d4d7cbbdd` |
| `easy_profiler.dll` | 185,344 | `ea0b226e00d9b715c77f02db5dcc7a5f22543128025327b31e71c02266bf826f` |
| `IHTAInstrumentation.dll` | 246,272 | `f271008543b2c798c8a18cd7bef13afe9a41ebc9c076b3bde53f8925335e708a` |
| `ITABase.dll` | 1,076,224 | `032e94eab29347eef58b6bf74203a13f36165829519e4a826ee28e54f3c484f1` |
| `ITAGeo.dll` | 840,192 | `578d78833c2b70007f7c66e98682b4f597dc6109b040a3589a71ef81e8baa124` |
| `ITAPropagationPathSim.dll` | 699,392 | `46bc08b9e3396e2f16d7625dd2f67156db3d3d006f10695f0ca1bf31f88a4247` |
| `OpenMeshCore.dll` | 487,424 | `73216d895efcfa17f5badc9a24c26fb0be3bce28b0427354a92ae8a89aba7f0f` |
| `samplerate.dll` | 1,492,992 | `594279dc691634ae1c4c65068641773a2e24ce8bb0ba19298a81059d55b97833` |
| `vista_aspects.dll` | 250,880 | `44943e3ad1817d17c9189d15d62819a10b9bc928131839bdf71089497662585b` |
| `vista_base.dll` | 441,856 | `54757902df1ccc1b2353e7d67c8a6055aaa84c246f70ab5f12553e8c580499a3` |
| `vista_inter_proc_comm.dll` | 674,816 | `900159f3d63bdbc98f7220256b5f3f50e15ba0d28197acbb7c1c95c9d466e66a` |
| `vista_math.dll` | 185,344 | `fa9984a053ce3185ea26d69df4c9420adeef0ac4ee5d30fa4a4638613616f18f` |
| `vista_tools.dll` | 391,680 | `9817ebddbd4263cad9866ef8fa394958e96b694ca6c4649f14c676e9ed3b5c49` |

Check them with `Get-FileHash <file> -Algorithm SHA256`.

## Licenses

The libraries in this folder are other people's software. Their license texts, the
source locations and the exact source revisions are in
[THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

## Order in which the toolbox looks for ART

1. the directories in `ART_DLL_DIR` / `ART_PYD_DIR`;
2. `bin/` (what `tools/build_art.ps1` writes, so your own build wins);
3. this folder, `prebuilt/win-x64-py313/`, when the platform and Python version match;
4. the in-tree build output.

## Updating these files

After rebuilding, copy the 15 files from `bin/` over this folder and refresh the
table above. Git stores every version of every file forever, so each update adds
about 13 MB to the size of the repository: update this folder only when ART
really changed.

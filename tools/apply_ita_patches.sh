#!/usr/bin/env bash
#
# Apply the Auralization-toolbox local modifications to the
# ITAGeometricalAcoustics submodules. POSIX counterpart of
# apply_ita_patches.ps1 - see that file for the rationale.
#
# Idempotent: a patch that is already applied is skipped. Patches are applied
# with --ignore-whitespace so they work whether the submodules were checked
# out with LF or CRLF endings.
#
#   ./tools/apply_ita_patches.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH_DIR="$REPO_ROOT/patches/ita"
ITA_ROOT="$REPO_ROOT/ITAGeometricalAcoustics"

if [ ! -f "$ITA_ROOT/CMakePresets.json" ]; then
    echo "ITAGeometricalAcoustics is not checked out." >&2
    echo "Run: git submodule update --init --recursive" >&2
    exit 1
fi

# submodule-relative-path:patch-file. The order matters: a patch may build on an
# earlier one for the same submodule (ITAGeo-unix.patch).
TARGETS=(
    ".:ITAGeometricalAcoustics.patch"
    "ITAGeo:ITAGeo.patch"
    "ITAGeo:ITAGeo-unix.patch"
    "ITAPropagationModels:ITAPropagationModels.patch"
)

failed=()

for entry in "${TARGETS[@]}"; do
    sub="${entry%%:*}"
    patch_name="${entry#*:}"
    patch="$PATCH_DIR/$patch_name"
    if [ "$sub" = "." ]; then
        dir="$ITA_ROOT"; label="ITAGeometricalAcoustics"
    else
        dir="$ITA_ROOT/$sub"; label="$sub"
    fi
    label="$label [$patch_name]"

    [ -f "$patch" ] || { echo "Missing patch file: $patch" >&2; exit 1; }
    if [ ! -d "$dir" ]; then
        echo "Submodule '$label' is not checked out. Run: git submodule update --init --recursive" >&2
        exit 1
    fi

    if git -C "$dir" apply --reverse --check --ignore-whitespace "$patch" 2>/dev/null; then
        echo "  [skip]  $label - already applied"
        continue
    fi

    if ! git -C "$dir" apply --check --ignore-whitespace "$patch" 2>/dev/null; then
        echo "  [FAIL]  $label - patch does not apply"
        failed+=("$label")
        continue
    fi

    if git -C "$dir" apply --ignore-whitespace --whitespace=nowarn "$patch"; then
        echo "  [ok]    $label - patched"
    else
        echo "  [FAIL]  $label - apply failed"
        failed+=("$label")
    fi
done

if [ ${#failed[@]} -gt 0 ]; then
    echo "" >&2
    echo "Could not patch: ${failed[*]}." >&2
    echo "The submodule may be at a different commit than expected (git submodule status)," >&2
    echo "or already locally modified." >&2
    exit 1
fi

# --- New files not part of any upstream file (copied verbatim) ------------
if [ -d "$PATCH_DIR/files" ]; then
    for subdir in "$PATCH_DIR/files"/*/; do
        [ -d "$subdir" ] || continue
        name="$(basename "$subdir")"
        # files/ITAGeometricalAcoustics/... lands in the ITA root, the other folders in the
        # submodule of the same name
        if [ "$name" = "ITAGeometricalAcoustics" ]; then dest="$ITA_ROOT"; else dest="$ITA_ROOT/$name"; fi
        if [ ! -d "$dest" ]; then
            echo "Submodule '$name' is not checked out." >&2
            exit 1
        fi
        while IFS= read -r -d '' src; do
            rel="${src#"$subdir"}"
            mkdir -p "$dest/$(dirname "$rel")"
            cp -f "$src" "$dest/$rel"
            echo "  [ok]    $name/$rel"
        done < <(find "$subdir" -type f -print0)
    done
fi

# --- Preflight: every referenced patch file must exist --------------------
missing=()
while IFS= read -r -d '' cmake_file; do
    case "$cmake_file" in */out/*) continue ;; esac
    while IFS= read -r ref; do
        [ -n "$ref" ] || continue
        if [ ! -f "$(dirname "$cmake_file")/patches/$ref" ]; then
            missing+=("${cmake_file#"$ITA_ROOT"/} -> patches/$ref")
        fi
    done < <(grep -oE 'patches/[A-Za-z0-9._-]+\.(cmake|patch)' "$cmake_file" 2>/dev/null \
             | sed 's|^patches/||' | sort -u)
done < <(find "$ITA_ROOT" -name CMakeLists.txt -type f -print0)

if [ ${#missing[@]} -gt 0 ]; then
    echo ""
    echo "WARNING: these CMake files reference patch files that do not exist."
    echo "         A fresh CMake configure will fail at the dependency populate step."
    printf '         %s\n' "${missing[@]}"
fi

echo ""
echo "ITA patches applied."

# Changes made to the MATLAB toolbox

Changes to the original MATLAB toolbox (`auralization_master`) that affect its results. They were needed so that MATLAB and Python can be compared fairly. All are already applied.

## 1. `attenuation_db` was never read

**File:** `auralization/MASTER_auralization_EngineAirframe.m`

The code checked for a field called `AttenuationdB`, which never exists: `ini2struct` turns every key into lower case, so the field is `attenuation_db`. MATLAB therefore always used 0 dB, whatever the `.ini` said.

```matlab
if isfield( input_file, 'attenuation_db' )
    AttenuationdB = str2double ( input_file.attenuation_db );
```

Effect: any `.ini` that sets `attenuation_db` now changes the level and file name of the written `.wav`.

## 2. Wind parameters are now read from the `.ini`

**File:** `auralization/private/get_propagation.m`

The four wind-parameter lines were commented out, and the direction line could never work (`str2double('[1 0 0]')` is `NaN`). They are now read only when the key exists, so existing `.ini` files keep the ART defaults.

```matlab
if isfield( input_file, 'const_wind_velocity' )
    atmos.constWindVelocity = str2double( input_file.const_wind_velocity );   % [m/s]
end
if isfield( input_file, 'const_wind_direction' )
    atmos.constWindDirection = str2num( input_file.const_wind_direction );    % [x y z]
end
if isfield( input_file, 'surface_roughness' )
    atmos.surfaceRoughness = str2double( input_file.surface_roughness );      % [m]
end
if isfield( input_file, 'friction_velocity' )
    atmos.frictionVelocity = str2double( input_file.friction_velocity );      % [m/s]
end
```

ART defaults when a key is missing: constant wind 20 m/s along +x; log wind with friction velocity 0.6 m/s, roughness 0.1 m, direction +x. A direction that is not a unit vector is normalised by ART, with a warning.

## 3. Removed a diagnostic HRIR call

**File:** `auralization/private/get_FIR.m`

A test call to `AKhrirInterpolation` (`[hrir_test_l, hrir_test_r] = ...`, followed by a `save` and an `fprintf`) ran on every run, even for mono scenarios. It was deleted. It had no effect on the results.

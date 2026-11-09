%% export_propagation_matlab.m
%  Paste this block into get_propagation.m, right AFTER:
%      OUT.TF = TF;
%  and BEFORE:
%      clear idx_reflection hypotenuse;
%
%  Then run compare_propagation.py to compare Python vs MATLAB vectors.
%% ---- begin paste block ----

% Rename to match Python .npz keys expected by compare_propagation.py
spherical_direct = launchAngle_direct_spherical;               % (N x 2)
spherical_reflected = launchAngle_reflected_spherical;          % (N x 2)
spherical_reflected_smooth = launchAngle_reflected_spherical_smooth; % (N x 2)

% Extract TF at overhead position (complex-valued)
tf_overhead_individual = TF{overhead_idx,1}.freq(:,1:2);       % (nFreq x 2) [direct, reflected]
tf_overhead_combined   = TF{overhead_idx,1}.freq(:,3);         % (nFreq x 1) combined

save('verification/propagation/propagation_matlab.mat', ...
    'time', 'freq', ...
    'thetaReflectedRay', 'propDistanceReflectedRay', ...
    'propagation_time', ...
    'launchAngle_direct', 'launchAngle_reflected', ...
    'spherical_direct', 'spherical_reflected', ...
    'spherical_reflected_smooth', ...
    'overhead_idx', ...
    'tf_overhead_individual', 'tf_overhead_combined');

fprintf('[VERIFICATION] Saved propagation_matlab.mat\n');

%% ---- end paste block ----

function verif_save(step, fileName, varargin)
% function verif_save(step, fileName, 'var1', 'var2', ...)
%
% Saves the named variables of the CALLING workspace to
%     <verification_root>/<step>/<fileName>
% so MATLAB writes the same per-scenario layout as the Python toolbox:
%     verification/scenarios/<scenario>/<step>/<fileName>
%
% <verification_root> is the global set by auralization_master (5th input).
% If it is empty, nothing is saved (verification is opt-in, like the Python
% --verification flag).
%
% Files are written with -v7 so scipy.io.loadmat can read them.
%
% Copy this file into <matlab toolbox>/utilities/.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

global verification_root

if isempty(verification_root)
    return
end

folder = fullfile(verification_root, step);
if ~exist(folder, 'dir')
    mkdir(folder);
end

S = struct();
for k = 1:numel(varargin)
    name = varargin{k};
    % like the built-in save: a missing variable is a warning, not an error, so the run continues
    % (verification/check_scenario_complete.py will report the missing key)
    if ~evalin('caller', sprintf('exist(''%s'',''var'')', name))
        warning('verif_save:missingVariable', ...
                'Variable <%s> requested for %s/%s does not exist in the calling workspace; skipped.', name, step, fileName);
        continue
    end
    S.(name) = evalin('caller', name);
end

target = fullfile(folder, fileName);
save(target, '-struct', 'S', '-v7');
fprintf('[VERIFICATION] Saved %s\n', target);

end

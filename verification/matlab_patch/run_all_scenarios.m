function run_all_scenarios(only, verification_base)
% function run_all_scenarios(only, verification_base)
%
% Runs the MATLAB auralization for every input_data/scenarios/*.ini in chain and
% writes the verification dumps to
%     <verification_base>/<scenario>/<step>/<file>.mat
% which is the folder the Python side (verification/run_scenarios.py) uses.
%
% INPUTS (both optional)
%   only : cell array of scenario numbers / name substrings, e.g. {'1','3'} or {2}
%          (default: all scenarios)
%   verification_base : folder holding one sub-folder per scenario
%          (default: C:\Dev\Auralization-toolbox\verification\scenarios)
%
% Run it from the MATLAB toolbox root (the folder containing auralization_master.m):
%     run_all_scenarios
%     run_all_scenarios({'1','3'})
%
% Afterwards, on the Python side:
%     python verification/run_scenarios.py --skip-run
%
% Copy this file into the MATLAB toolbox root, next to auralization_master.m.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

if nargin < 1, only = {}; end
if nargin < 2
    verification_base = 'C:\Dev\Auralization-toolbox\verification\scenarios';
end
if ~iscell(only), only = num2cell(only); end

root = fileparts(mfilename('fullpath'));
% startup_auralization adds its folders with RELATIVE paths, so it must run from the toolbox root
old_dir = cd(root);
restore_dir = onCleanup(@() cd(old_dir));
startup_auralization;

main_input_path = fullfile(root, 'input_data');   % holds auralization_input.dat + geschw_hoehe_verlauf.dat
inis = dir(fullfile(main_input_path, 'scenarios', '*.ini'));

status = {};
for k = 1:numel(inis)

    [~, name] = fileparts(inis(k).name);

    % select by number ("scenario_<n>_...") or by name substring
    if ~isempty(only)
        keep = false;
        for j = 1:numel(only)
            token = only{j};
            if isnumeric(token), token = num2str(token); end
            if all(isstrprop(token, 'digit'))
                keep = keep || startsWith(name, ['scenario_' token '_']);
            else
                keep = keep || contains(name, token);
            end
        end
        if ~keep, continue; end
    end

    fprintf('\n%s\n# %s\n%s\n', repmat('#', 1, 90), name, repmat('#', 1, 90));

    ini_path     = fullfile(inis(k).folder, inis(k).name);
    % NOTE: create_auralization_results_folder concatenates strings, so results_path MUST end with a separator
    results_path = [fullfile(root, 'results_auralization', name) filesep];
    vroot        = fullfile(verification_base, name);

    % remove stale MATLAB dumps of this scenario (Python dumps are left alone)
    if exist(vroot, 'dir')
        stale = dir(fullfile(vroot, '**', '*_matlab.mat'));
        stale = [stale; dir(fullfile(vroot, '**', '*_MATLAB.mat')); dir(fullfile(vroot, '**', 'MATLAB_trimmed_output.mat')); ...
                 dir(fullfile(vroot, '**', 'tones_spl_debug_matlab_*.mat'))];
        for s = 1:numel(stale), delete(fullfile(stale(s).folder, stale(s).name)); end
    end

    % a scenario with its own source data has a folder input_data/scenario_inputs/<scenario>
    input_path = fullfile(main_input_path, 'scenario_inputs', name);
    if ~exist(input_path, 'dir'), input_path = main_input_path; end

    try
        tic;
        auralization_master(input_path, name, ini_path, results_path, vroot);
        status{end+1} = sprintf('%-45s ok      (%.0f s)', name, toc); %#ok<AGROW>
    catch ME
        status{end+1} = sprintf('%-45s FAILED  %s', name, ME.message); %#ok<AGROW>
        fprintf(2, 'Scenario %s failed:\n%s\n', name, getReport(ME));
    end

    close all;
end

fprintf('\n%s\nMATLAB SCENARIO CHAIN SUMMARY\n%s\n', repmat('=', 1, 90), repmat('=', 1, 90));
fprintf('%s\n', status{:});
fprintf('Next: python verification/run_scenarios.py --skip-run\n');

end

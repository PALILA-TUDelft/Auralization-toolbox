%% export_apply_propagation_matlab.m
%  Paste this block into apply_propagation.m, right AFTER:
%      outputSignal.outputSignal = overlapp_add_convolution( inputSignal, BlockLen, FIR.impulseResponse, 'mono' );
%  and BEFORE the binaural section.
%
%  Then run:  python verification/apply_propagation/compare_apply_propagation.py
%% ---- begin paste block ----

ir            = FIR.impulseResponse;
output_signal = outputSignal.outputSignal;
input_signal  = inputSignal;
block_len     = BlockLen;

save('verification/apply_propagation/apply_propagation_matlab.mat', ...
    'ir', 'output_signal', 'input_signal', 'block_len');

fprintf('[VERIFICATION] Saved apply_propagation_matlab.mat\n');

%% ---- end paste block ----

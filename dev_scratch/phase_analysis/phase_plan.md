# Analysis plan for forcing effects with periodically masked signals

## 1. Goal and constraints

The goal is to determine how periodic forcing changes ongoing oscillatory activity, especially whether it mainly:

- aligns or frequency-locks spontaneous activity to the forcing frequency $f_0$;
- concentrates broad spontaneous power around $f_0$;
- adds extra oscillatory energy, as in ringing;
- produces a mixture of these effects.

Important constraints:

- Samples around every pulse must be rejected.
- The periodic mask strongly distorts the absolute fitted spectrum and phase distribution.
- Spontaneous activity may be colored, nonstationary, and approximately $1/f$, with unknown parameters.
- The number of independent seeds is small.
- Each simulation is long and contains many pulses.
- Several pulse strengths are usually available, including zero.
- Pairing stimulated and spontaneous runs by seed may or may not be meaningful.

The central principle is:

$$
\boxed{
\text{Apply exactly the same event schedule, rejection mask, fitting method, and block structure to every pulse strength, including zero.}
}
$$

The absolute masked spectrum and absolute phase histogram are not reliable by themselves. The informative quantities are contrasts relative to the identically masked zero-strength condition.

---

## 2. Data organization

Let

$$
Y_{h,s,b,k}
$$

denote a quantity measured at pulse strength $h$, seed $s$, time block $b$, and pulse/event $k$.

Recommended hierarchy:

- **Pulse strength $h$:** zero and several nonzero strengths.
- **Seed $s$:** independent or partly independent simulation realizations.
- **Block $b$:** long nonoverlapping intervals within each simulation.
- **Event $k$:** individual pulses within a block.

### Block length

Use nonoverlapping blocks that:

- contain an integer number of stimulus periods;
- contain enough cycles to estimate the local spectrum;
- are longer than the main autocorrelation or coherence time.

A practical starting point is 5–10 s for a 5 Hz drive, then repeat with somewhat longer blocks as a robustness check.

### Pooling rules

For exploratory plots, all blocks and events can be shown. However:

- blocks from the same seed are not equivalent to independent seeds;
- events from the same block are strongly dependent;
- seeds with more blocks or valid events should not automatically receive more weight.

A seed-balanced average is preferable:

$$
\bar Y_h
=
\frac{1}{N_h}\sum_s
\left[
\frac{1}{B_{h,s}}\sum_b Y_{h,s,b}
\right].
$$

For phase densities, estimate one density per seed and then average those densities equally across seeds.

### Pairing

Use an **unpaired comparison as the default** if same-seed matching is questionable.

Also compute a paired-by-seed version as a sensitivity analysis when corresponding runs share an important fixed realization, such as the same connectivity matrix. Agreement between paired and unpaired summaries is reassuring.

Do not pair block $b$ in one condition with block $b$ in another unless the underlying noise trajectory is genuinely shared.

### Test data

**Root folder for simulation results (read-only):**

`exp_results/batch_rxbkg_state1_mech1/net_pulse_var_seed_f_amp`

**Root folder for analysis:**

`dev_scratch/artifacts/net_pulse_var_seed_f_amp`

Each subfodler is an experiment, their names match between source and analysis fodlers.

**Experiment to use for analysis debugging:**

`exp_L2_nseed_3_f_5_amp_0.001_0.02_5_t_5.0_50.0_lfp_0_300_50_ictrl_wmult_0.25_ee_0`



---

# Priority 1 — Simple, high-value visual analyses

## 3. Raw masked spectra plus zero-strength reference

For each strength $h$, compute the spectrum using the identical mask and fitting procedure:

$$
S_h(f).
$$

Plot all strengths together, including $h=0$.

This plot is mainly diagnostic. The mask-driven peak will probably dominate all curves, but it shows whether the artifact is similar across conditions and whether nonzero strengths produce systematic deviations.

### Main spectral contrast

Use the zero-strength condition as the empirical baseline:

$$
D_h(f)
=
\log S_h(f)-\log S_0(f)
=
\log\frac{S_h(f)}{S_0(f)}.
$$

The log ratio is preferable to a raw difference when spontaneous power changes strongly with frequency.

Recommended plot:

- one mean $D_h(f)$ curve per pulse strength;
- thin block-level or seed-level curves in the background;
- a thicker seed-balanced mean or median;
- mark $f_0$, the target band, and side bands.

Interpretation:

- positive near $f_0$, negative nearby: spectral concentration or frequency locking;
- positive across the whole oscillatory band: increased oscillatory energy;
- broad positive change: nonspecific activation;
- nonmonotonic changes with pulse strength: possible nonlinear locking regime.

---

## 4. Band power and spectral concentration

A peak increase at $f_0$ alone cannot distinguish locking from ringing.

Define:

- a broad analysis band $B=[f_1,f_2]$;
- a narrow target band $B_0$ around $f_0$;
- optional lower and upper side bands.

Calculate for each block:

### Total band power

$$
P_B(h)=\int_B S_h(f)\,df.
$$

### Target-band power

$$
P_0(h)=\int_{B_0} S_h(f)\,df.
$$

### Spectral concentration

$$
C_0(h)=\frac{P_0(h)}{P_B(h)}.
$$

### Spectral centroid

$$
f_c(h)=
\frac{\int_B fS_h(f)\,df}
{\int_B S_h(f)\,df}.
$$

### Spectral width

$$
\sigma_f^2(h)=
\frac{\int_B [f-f_c(h)]^2S_h(f)\,df}
{\int_B S_h(f)\,df}.
$$

Recommended visualization:

- x-axis: pulse strength;
- y-axis: $P_B$, $C_0$, $f_c-f_0$, or $\sigma_f$;
- small points: blocks;
- larger points or lines: seed means;
- thick line: seed-balanced condition mean.

Expected patterns:

### Locking or spectral concentration

$$
C_0\uparrow,\qquad
\sigma_f\downarrow,\qquad
f_c\rightarrow f_0,
$$

while

$$
P_B\approx\text{constant}.
$$

### Ringing or amplitude amplification

$$
P_B\uparrow.
$$

### Mixed response

$$
P_B\uparrow,\qquad
C_0\uparrow,\qquad
\sigma_f\downarrow.
$$

---

## 5. Raw phase-density overlays

The raw phase histogram is still useful if the zero-strength condition is shown as the empirical baseline.

For each strength, estimate

$$
p_h(\phi).
$$

Recommended visualization:

- show $p_0(\phi)$ as a thick gray or black curve;
- show nonzero strengths as colored curves;
- optionally show a block-derived envelope for $p_0(\phi)$;
- keep the physical phase axis, because it is interpretable relative to the stimulus.

The mask-induced two-peak pattern should appear in $p_0$. A forcing effect appears as a systematic redistribution away from that baseline.

Do not interpret the area below $p_0(\phi)$ as a literal “spontaneous component.” The two curves are probability densities, not an additive decomposition.

### Phase enrichment

Plot either

$$
\Delta p_h(\phi)=p_h(\phi)-p_0(\phi)
$$

or

$$
L_h(\phi)
=
\log
\frac{p_h(\phi)+\epsilon}
{p_0(\phi)+\epsilon}.
$$

Interpretation:

- $\Delta p_h>0$ or $L_h>0$: that phase is enriched by forcing;
- $\Delta p_h<0$ or $L_h<0$: that phase is depleted.

Use circular kernel-density estimates rather than dividing noisy histogram bins directly.

For multiple strengths, a useful summary is a phase-by-strength heat map of $\Delta p_h(\phi)$ or $L_h(\phi)$.

---

## 6. Per-stimulus complex coefficient clouds

For every pulse, keep the fitted complex coefficient

$$
z_k(f)=a_k(f)-ib_k(f).
$$

At $f_0$, plot each event in the plane

$$
(\operatorname{Re}z,\operatorname{Im}z)
=
(a,-b).
$$

This is one of the most useful visualizations because it shows amplitude, phase, anisotropy, and multimodality simultaneously.

Recommended cloud plot:

- one panel per pulse strength, or multiple transparent clouds overlaid;
- zero-strength cloud in gray;
- nonzero strengths in progressively stronger colors;
- show the mean vector for each strength;
- optionally show one cloud per block in faint lines and the pooled cloud in points.

Interpretation:

- same elliptical cloud but shifted mean: development of a coherent phase-locked component;
- same mean but narrower angular spread: stronger phase concentration;
- radial expansion: increased amplitude or power;
- rotation of the cloud: phase shift;
- nonlinear deformation or multiple lobes: more complex state dependence.

---

# Priority 2 — Corrected phase and geometry-aware analyses

## 7. Zero-strength covariance ellipses and Mahalanobis geometry

Estimate the zero-strength coefficient mean and covariance:

$$
\mu_0=
E
\begin{bmatrix}
\operatorname{Re}z\\
\operatorname{Im}z
\end{bmatrix},
\qquad
\Sigma_0=
\operatorname{Cov}
\begin{bmatrix}
\operatorname{Re}z\\
\operatorname{Im}z
\end{bmatrix}.
$$

For any event with coefficient vector

$$
v=
\begin{bmatrix}
\operatorname{Re}z\\
\operatorname{Im}z
\end{bmatrix},
$$

define the Mahalanobis radius

$$
Q=(v-\mu_0)^T\Sigma_0^{-1}(v-\mu_0).
$$

### Ellipse overlay

Overlay zero-strength Mahalanobis contours on every cloud plot:

$$
Q=q.
$$

Useful contours are empirical percentiles of the zero-strength distribution, for example:

- 50th percentile;
- 80th percentile;
- 95th percentile.

This is better than assuming that $Q$ follows an exact $\chi^2_2$ distribution, because spontaneous activity may be non-Gaussian.

Visual questions:

- Do nonzero-strength clouds extend beyond the spontaneous ellipses?
- Do they shift in one preferred direction?
- Does the shift grow smoothly with pulse strength?
- Does the cloud become more compact angularly but not more radial?
- Does the cloud cross the spontaneous ellipses mainly near one phase?

### Mahalanobis amplitude

Use $Q$, rather than Euclidean amplitude $|z|$, as a geometry-corrected measure of how unusual an event is relative to masked spontaneous activity.

Plot the distribution of $Q$ versus pulse strength.

---

## 8. Thresholded phase histograms

Thresholding can make phase structure easier to see, but threshold on Mahalanobis radius rather than raw amplitude.

Choose a threshold from the zero-strength empirical distribution:

$$
Q>Q_{0.5},\quad
Q>Q_{0.8},\quad
Q>Q_{0.9}.
$$

For every threshold, apply the same rule to all strengths.

Then plot

$$
p_h(\phi\mid Q>Q_{\rm threshold}).
$$

Important:

- also plot the thresholded zero-strength density;
- thresholding can change the spontaneous phase distribution;
- a high raw-amplitude threshold may exaggerate the mask-driven axis, whereas a Mahalanobis threshold compensates for the ellipse.

Recommended exploratory figure:

- rows: threshold level;
- columns: pulse strength;
- zero-strength baseline overlaid in every panel.

A robust forcing-related preferred phase should remain in approximately the same location across reasonable thresholds.

---

## 9. Whitened coefficient clouds and corrected phase

Transform coefficients using the zero-strength covariance:

$$
w=
\Sigma_0^{-1/2}(v-\mu_0).
$$

Under an approximately elliptical spontaneous null, the zero-strength cloud becomes close to circular.

Define the corrected angle

$$
\psi=\operatorname{atan2}(w_2,w_1).
$$

Recommended visualization:

- raw physical cloud and phase on the left;
- whitened cloud and corrected phase on the right.

The raw phase retains physical interpretation. The corrected phase reveals structure relative to the masked spontaneous geometry.

Use whitening mainly as a visualization and diagnostic, not as a replacement for the physical phase.

---

## 10. Null-flattened phase histogram

A more general nonparametric correction is to transform physical phase using the zero-strength circular cumulative distribution:

$$
u=2\pi F_0(\phi).
$$

By construction, zero-strength phases are uniform in $u$.

Apply the same transformation to all nonzero strengths.

Recommended plot:

- zero-strength corrected histogram, which should be approximately flat;
- corrected histograms for each pulse strength;
- optional phase-by-strength heat map.

This removes the exact empirical two-peak baseline without assuming that the coefficient cloud is Gaussian.

Caution: the transformed angle $u$ is not the original physical phase. Use it to visualize enrichment, while retaining raw phase plots for interpretation.

---

# Priority 2 — Coherence and event-locking decompositions

## 11. Total and coherent coefficient power

For each block and frequency, calculate

$$
P_{\rm total}(f)
=
\frac{1}{K}\sum_k|z_k(f)|^2,
$$

$$
P_{\rm coherent}(f)
=
\left|
\frac{1}{K}\sum_k z_k(f)
\right|^2,
$$

and

$$
F_{\rm coherent}(f)
=
\frac{P_{\rm coherent}(f)}
{P_{\rm total}(f)}.
$$

Interpretation:

- $P_{\rm total}$: average event-level oscillatory magnitude;
- $P_{\rm coherent}$: phase-aligned mean component;
- $F_{\rm coherent}$: fraction of coefficient power organized into a common phase.

Compare all three against the zero-strength condition.

A locking-dominated effect can increase $P_{\rm coherent}$ and $F_{\rm coherent}$ with little change in $P_{\rm total}$.

A ringing or amplitude effect is more likely to increase $P_{\rm total}$ as well.

Because the mask also affects $z_k$, use these quantities comparatively, not absolutely.

---

## 12. First- and second-harmonic phase concentration

For unit phase vectors

$$
u_k=\frac{z_k}{|z_k|},
$$

calculate

$$
R_1=
\left|
\frac{1}{K}\sum_k u_k
\right|,
$$

$$
R_2=
\left|
\frac{1}{K}\sum_k u_k^2
\right|.
$$

The mask-driven antipodal two-peak pattern tends to produce:

$$
R_2>0,\qquad R_1\approx0.
$$

A single preferred forcing phase should increase $R_1$.

Plot $R_1$ and $R_2$ versus pulse strength, using one value per block and seed-balanced summaries.

Use these as descriptive diagnostics. Amplitude-weighted quantities such as the mean complex vector and coherent power are usually more reliable than unit-vector ITC when many events have weak amplitudes.

---

# Priority 3 — More diagnostic but more involved analyses

## 13. Additive ringing prediction

If simulations are available for:

- baseline $x_0(t)$;
- noise only $x_N(t)$;
- pulses only $x_P(t)$;
- noise plus pulses $x_{NP}(t)$;

then construct the linear additive prediction

$$
x_{\rm add}(t)
=
x_N(t)+x_P(t)-x_0(t).
$$

Define the interaction residual

$$
I(t)
=
x_{NP}(t)-x_N(t)-x_P(t)+x_0(t).
$$

For purely additive ringing in a linear system,

$$
I(t)\approx0.
$$

Phase reset, frequency pulling, or state-dependent forcing generally produce

$$
I(t)\neq0.
$$

Apply the same rejection mask to all signals.

Useful visualizations:

- spectrum of $x_{NP}$ versus spectrum of $x_{\rm add}$;
- log spectral ratio $S_{NP}/S_{\rm add}$;
- spectrum of $I(t)$;
- peri-stimulus average of $I(t)$ outside the rejected window;
- per-event complex cloud of $I(t)$.

This is a strong mechanistic diagnostic if the required conditions are available.

---

## 14. Time-resolved spectral evolution

To see whether locking develops gradually:

- calculate blockwise or sliding-window spectra;
- plot target-band concentration $C_0(t)$;
- plot coherent fraction $F_{\rm coherent}(t)$;
- plot the mean complex vector over time.

Possible patterns:

- gradual narrowing toward $f_0$: entrainment buildup;
- abrupt jump: nonlinear capture;
- oscillation between locked and unlocked states: noisy phase slips;
- post-stimulus decay of excess power: ringing.

Because sliding windows overlap, treat these plots as visual trajectories, not independent samples.

---

## 15. Phase-slip and locking-duration analysis

For stronger forcing, unwrap the estimated phase relative to the drive:

$$
\psi(t)=\theta(t)-2\pi f_0 t.
$$

Look for:

- plateaus in $\psi(t)$: locked periods;
- $2\pi$ jumps: phase slips;
- decreasing slip rate with pulse strength;
- concentration of $\psi$ around a stable phase.

This is useful when the system moves in and out of a noisy Arnold tongue. It is more demanding because phase estimation with gaps must be stable over time.

---

# Priority 4 — Statistical refinements, optional during exploration

## 16. Blockwise unpaired comparisons

With few seeds and long simulations, use blocks to show temporal variability.

For every block, compute:

- $P_B$;
- $C_0$;
- $\sigma_f$;
- $P_{\rm coherent}$;
- $F_{\rm coherent}$;
- $R_1$;
- mean Mahalanobis radius $Q$.

Show all block values, grouped by seed and pulse strength.

For exploratory comparisons, use:

- medians and interquartile ranges;
- bootstrap intervals obtained by resampling blocks within seeds;
- unpaired permutation or Mann–Whitney tests only as descriptive supplements.

Do not present the total number of blocks as the number of independent simulation realizations.

---

## 17. Hierarchical bootstrap

A two-level bootstrap can combine the small number of seeds with the large number of blocks.

For each bootstrap replicate:

1. resample seeds;
2. within each selected seed, resample blocks;
3. recompute the condition summary or contrast.

For an unpaired analysis, resample seeds independently for each pulse strength.

For an optional seed-paired sensitivity analysis, resample seed pairs but resample blocks independently within the two runs.

This provides exploratory uncertainty bands while respecting the hierarchy better than pooling all blocks as independent.

---

## 18. Paired versus unpaired sensitivity analysis

Because seed pairing is questionable, compute both when possible.

### Unpaired primary summary

Compare seed-balanced distributions across strengths without matching seeds.

### Paired sensitivity summary

For seeds that share connectivity or another meaningful realization, calculate within-seed differences:

$$
D_s(h)=Y_{h,s}-Y_{0,s}.
$$

Agreement between the paired and unpaired conclusions is more informative than either result alone.

If they disagree strongly, inspect whether:

- the pairing removed large between-network variation;
- paired runs do not actually share meaningful randomness;
- one or two seeds dominate;
- the effect depends on baseline spontaneous dynamics.

---

# 19. Recommended figure set

## Figure 1 — Masked spectra and relative spectra

- Raw masked spectra for all pulse strengths.
- Log ratio relative to zero strength.
- Mark $f_0$, target band, and side bands.

## Figure 2 — Spectral redistribution versus total energy

Plot versus pulse strength:

- total band power $P_B$;
- target concentration $C_0$;
- spectral width $\sigma_f$;
- centroid offset $f_c-f_0$.

Show blocks, seed means, and seed-balanced summary.

## Figure 3 — Raw phase distributions

- $p_0(\phi)$ as the empirical masked spontaneous baseline.
- $p_h(\phi)$ for all nonzero strengths.
- Spontaneous block envelope.
- Optional phase-enrichment heat map $\Delta p_h(\phi)$.

## Figure 4 — Per-stimulus coefficient clouds

At $f_0$:

- event-level $(a,-b)$ points;
- zero-strength covariance ellipse;
- empirical Mahalanobis percentile ellipses;
- mean vector for each pulse strength;
- optional arrows showing movement of the mean with strength.

## Figure 5 — Corrected phase geometry

- whitened coefficient clouds;
- corrected phase histogram;
- or null-flattened phase histogram $u=2\pi F_0(\phi)$;
- thresholded versions based on $Q$.

## Figure 6 — Coherent versus total activity

Versus pulse strength:

- $P_{\rm total}$;
- $P_{\rm coherent}$;
- $F_{\rm coherent}$;
- $R_1$ and $R_2$.

## Figure 7 — Additive prediction, if available

- actual noise-plus-pulse spectrum;
- additive prediction;
- interaction-residual spectrum;
- interaction-residual peri-stimulus waveform.

---

# 20. Minimal top-priority workflow

A compact first implementation should include:

1. Split each simulation into long nonoverlapping blocks.
2. Apply the identical periodic mask to every pulse strength, including zero.
3. Compute one spectrum per block.
4. Plot raw spectra and log spectra relative to zero strength.
5. Calculate $P_B$, $C_0$, $f_c$, and $\sigma_f$ per block.
6. Fit event-level complex coefficients $z_k=a_k-ib_k$ at $f_0$.
7. Plot per-event coefficient clouds for each strength.
8. Estimate $\mu_0$ and $\Sigma_0$ from zero-strength events.
9. Overlay empirical Mahalanobis ellipses on every cloud.
10. Plot raw phase densities over the zero-strength density.
11. Plot phase enrichment $\Delta p_h(\phi)$ or $\log[p_h/p_0]$.
12. Plot $P_{\rm coherent}$, $P_{\rm total}$, and $F_{\rm coherent}$ versus strength.
13. Show block-level variability and seed means; use unpaired seed-balanced summaries by default.
14. Repeat key results with a slightly wider rejection mask and a different block length.

This set should already distinguish:

- mask artifacts shared by all conditions;
- phase enrichment relative to masked spontaneous activity;
- spectral concentration around $f_0$;
- increased total oscillatory energy;
- coherent phase locking;
- pulse-strength dependence.

---

# 21. Interpretation guide

## Mostly locking or spectral concentration

Expected combination:

$$
C_0\uparrow,\qquad
\sigma_f\downarrow,\qquad
f_c\rightarrow f_0,
$$

$$
P_B\approx\text{constant},
$$

$$
P_{\rm coherent}\uparrow,
$$

with the complex cloud becoming more directionally organized.

## Mostly additive ringing

Expected combination:

$$
P_B\uparrow,
$$

$$
P_{\rm total}\uparrow,
$$

and, when the additive prediction is available,

$$
x_{NP}\approx x_N+x_P-x_0.
$$

## Mixed nonlinear forcing

Expected combination:

$$
P_B\uparrow,\qquad
C_0\uparrow,\qquad
P_{\rm coherent}\uparrow,
$$

with a nonzero interaction residual and strength-dependent deformation or displacement of the coefficient cloud.

## Mask-dominated apparent effect

Warning signs:

- the same spectral peak and phase peaks appear at zero strength;
- the preferred phases rotate when the rejection-window center is shifted;
- raw-amplitude thresholding strengthens the same antipodal peaks;
- the effect disappears in log-ratio, enrichment, whitening, or Mahalanobis-corrected plots;
- the apparent effect changes strongly with small changes in mask width while condition contrasts do not remain stable.

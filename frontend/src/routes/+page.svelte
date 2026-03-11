<script lang="ts">
	import { tick } from 'svelte';
	import { api } from '$lib/api';
	import { isLoggedIn } from '$lib/stores/auth';
	import { goto } from '$app/navigation';

	type ChatMsg = { role: 'user' | 'assistant'; content: string };

	let messages = $state<ChatMsg[]>([
		{ role: 'assistant', content: 'What are you looking for? Describe what you want to buy, sell, find, or do.' }
	]);
	let input = $state('');
	let sending = $state(false);
	let submitted = $state(false);
	let messagesEl: HTMLDivElement;

	// Trace popup state
	let showTrace = $state(false);
	let traceQueryId = $state<string | null>(null);
	let trace = $state<any>(null);
	let tracePolling = $state(false);
	let traceTimeout = $state(false);

	function conversationHistory() {
		return messages.map(m => ({ role: m.role, content: m.content }));
	}

	async function scrollToBottom() {
		await tick();
		if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
	}

	async function send() {
		const text = input.trim();
		if (!text || sending || submitted) return;

		messages = [...messages, { role: 'user', content: text }];
		input = '';
		sending = true;
		await scrollToBottom();

		try {
			const res = await api.converse(conversationHistory());
			if (res.action === 'submitted') {
				messages = [...messages, { role: 'assistant', content: res.message || 'Query submitted! Looking for matches now.' }];
				submitted = true;
				if (res.query_id) {
					traceQueryId = res.query_id;
					showTrace = true;
					pollTrace(res.query_id);
				}
			} else {
				messages = [...messages, { role: 'assistant', content: res.message || 'Could you tell me more?' }];
			}
		} catch (e: any) {
			messages = [...messages, { role: 'assistant', content: `Something went wrong: ${e.message}` }];
		} finally {
			sending = false;
			await scrollToBottom();
		}
	}

	async function pollTrace(queryId: string, attempts = 0) {
		if (attempts > 20) {
			traceTimeout = true;
			tracePolling = false;
			return;
		}
		tracePolling = true;
		try {
			const result = await api.getMatchTrace(queryId);
			if (result.ready) {
				trace = result.trace;
				tracePolling = false;
			} else {
				setTimeout(() => pollTrace(queryId, attempts + 1), 1500);
			}
		} catch {
			tracePolling = false;
		}
	}

	function closeTrace() {
		showTrace = false;
	}

	function reset() {
		messages = [{ role: 'assistant', content: 'What are you looking for? Describe what you want to buy, sell, find, or do.' }];
		submitted = false;
		input = '';
		showTrace = false;
		traceQueryId = null;
		trace = null;
		tracePolling = false;
		traceTimeout = false;
	}

	function stepIcon(status: string) {
		return status === 'pass' ? '✓' : '✗';
	}

	function matchCount() {
		if (!trace) return 0;
		const step = trace.steps?.find((s: any) => s.step === 'matches_created');
		return step?.count ?? 0;
	}
</script>

{#if !$isLoggedIn}
	<!-- HERO -->
	<section class="hero">
		<div class="hero-content">
			<h1 class="serif hero-title">
				Find exactly<br />
				<em class="gold-word">who you need,</em><br />
				instantly.
			</h1>
			<p class="hero-sub">Describe what you're looking for. Our AI matches you with the right people — in seconds, not days.</p>
			<div class="hero-ctas">
				<a href="/login" class="btn-outline">See how it works</a>
				<a href="/login" class="btn-primary">Get started free</a>
			</div>
		</div>

		<!-- Central card -->
		<div class="hero-diagram">
			<svg class="diagram-svg" viewBox="0 0 700 480" xmlns="http://www.w3.org/2000/svg">
				<defs>
					<linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
						<stop offset="0%" stop-color="#c9b8a0" />
						<stop offset="100%" stop-color="#a78b71" />
					</linearGradient>
					<linearGradient id="lineGrad2" x1="0%" y1="0%" x2="100%" y2="100%">
						<stop offset="0%" stop-color="#a78b71" />
						<stop offset="100%" stop-color="#c9b8a0" />
					</linearGradient>
				</defs>
				<!-- Lines from satellite cards to center -->
				<!-- Top-left card (150,100) to center (350,240) -->
				<path d="M 230 130 C 270 130 310 210 350 230" stroke="url(#lineGrad)" stroke-width="2.5" fill="none" class="node-line" />
				<path d="M 200 145 C 250 155 310 220 348 235" stroke="url(#lineGrad)" stroke-width="1" fill="none" stroke-dasharray="5 15" class="node-line" style="animation-delay: 0.3s" />
				<!-- Right card (520,200) to center (350,240) -->
				<path d="M 490 220 C 450 220 400 230 370 238" stroke="url(#lineGrad2)" stroke-width="2.5" fill="none" class="node-line" style="animation-delay: 0.5s" />
				<path d="M 490 235 C 445 240 405 242 372 242" stroke="url(#lineGrad2)" stroke-width="1" fill="none" stroke-dasharray="5 15" class="node-line" style="animation-delay: 0.8s" />
				<!-- Bottom-left card (140,360) to center (350,260) -->
				<path d="M 220 355 C 270 320 310 280 348 258" stroke="url(#lineGrad)" stroke-width="2.5" fill="none" class="node-line" style="animation-delay: 0.2s" />
				<path d="M 205 340 C 260 310 315 285 349 262" stroke="url(#lineGrad)" stroke-width="1" fill="none" stroke-dasharray="5 15" class="node-line" style="animation-delay: 0.6s" />
			</svg>

			<!-- Center card -->
			<div class="center-card glass">
				<div class="center-card-logo serif">MM</div>
				<div class="center-card-label">MatchMaker</div>
				<div class="center-card-sub">AI Matching Engine</div>
			</div>

			<!-- Satellite 1: top-left — Vector Search -->
			<div class="sat-card sat-top-left glass">
				<div class="sat-icon">&#9670;</div>
				<div class="sat-title">Vector Search</div>
				<div class="sat-stat">384-dim embeddings</div>
				<div class="sat-bar"><div class="sat-bar-fill" style="width:78%"></div></div>
				<div class="sat-score">78% similarity</div>
			</div>

			<!-- Satellite 2: right — AI Matching -->
			<div class="sat-card sat-right glass">
				<div class="sat-icon">&#10024;</div>
				<div class="sat-title">AI Scoring</div>
				<div class="sat-stat">Compatibility</div>
				<div class="sat-score-big">94%</div>
			</div>

			<!-- Satellite 3: bottom-left — Live Match -->
			<div class="sat-card sat-bottom-left glass">
				<div class="sat-pill" style="animation: breathing 2.4s ease-in-out infinite">
					<span class="pill-dot"></span>
					Live Match Found
				</div>
				<div class="sat-match-text">"Looking for a Svelte dev..."</div>
			</div>
		</div>
	</section>

	<!-- FEATURES -->
	<section class="features">
		<div class="features-grid">
			<div class="feature-card glass">
				<div class="feature-icon">
					<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/><path d="m21 21-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
				</div>
				<h3>Semantic Search</h3>
				<p>Vector embeddings understand intent, not just keywords. Find matches others miss.</p>
			</div>
			<div class="feature-card glass">
				<div class="feature-icon">
					<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="m2 17 10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="m2 12 10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
				</div>
				<h3>AI Scoring</h3>
				<p>An LLM evaluates every candidate and scores compatibility — so you only see quality matches.</p>
			</div>
			<div class="feature-card glass">
				<div class="feature-icon">
					<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
				</div>
				<h3>Real-time Chat</h3>
				<p>WebSocket-powered messaging so you can connect with matches the moment they're found.</p>
			</div>
			<div class="feature-card glass">
				<div class="feature-icon">
					<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><polyline points="22,4 12,14.01 9,11.01" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
				</div>
				<h3>Smart Matching</h3>
				<p>Two-stage pipeline: vector pre-filter then LLM refinement. Fast and accurate.</p>
			</div>
		</div>
	</section>

	<!-- FOOTER -->
	<footer class="site-footer">
		<div class="footer-inner">
			<div class="footer-col">
				<span class="serif footer-logo">MatchMaker</span>
				<p class="footer-tagline">AI-powered query matching for the modern web.</p>
			</div>
			<div class="footer-col">
				<a href="/login">Get started</a>
				<a href="/login">Sign in</a>
				<a href="/queries">Queries</a>
				<a href="/messages">Messages</a>
			</div>
			<div class="footer-col">
				<p class="footer-label">Join the digest</p>
				<div class="footer-input-row">
					<input type="email" placeholder="you@example.com" />
					<button class="footer-submit btn-primary" aria-label="Subscribe">&#8250;</button>
				</div>
			</div>
		</div>
		<div class="footer-bottom">
			<span>&copy; 2026 MatchMaker. All rights reserved.</span>
		</div>
	</footer>

{:else}
	<!-- LOGGED IN: Dark chat UI -->
	<div class="page-header">
		<div>
			<h1 class="serif">Create a query</h1>
			<p>Tell us what you're looking for. We'll find your match.</p>
		</div>
	</div>

	<div class="chat-panel glass">
		<div class="chat-messages" bind:this={messagesEl}>
			{#each messages as msg, i (i)}
				<div class="msg" class:msg-user={msg.role === 'user'}>
					<div class="msg-bubble" class:bubble-user={msg.role === 'user'}>
						{msg.content}
					</div>
				</div>
			{/each}
			{#if sending}
				<div class="msg">
					<div class="msg-bubble typing">
						<span class="dot"></span><span class="dot"></span><span class="dot"></span>
					</div>
				</div>
			{/if}
		</div>

		{#if submitted}
			<div class="success-bar">
				<div class="success-icon">&#10003;</div>
				<span>Query created successfully</span>
				<div class="success-actions">
					{#if traceQueryId}
						<button class="btn-secondary btn-sm" onclick={() => { showTrace = true; }}>View matching</button>
					{/if}
					<button class="btn-secondary btn-sm" onclick={reset}>New query</button>
					<button class="btn-primary btn-sm" onclick={() => goto('/queries')}>View queries</button>
				</div>
			</div>
		{:else}
			<form class="chat-input" onsubmit={(e) => { e.preventDefault(); send(); }}>
				<input
					type="text"
					bind:value={input}
					placeholder="e.g. I want to sell my MacBook Pro 16 inch..."
					disabled={sending}
				/>
				<button class="btn-gold send-btn" type="submit" disabled={sending || !input.trim()}>
					Send
				</button>
			</form>

		{/if}
	</div>
{/if}

<!-- Matching Trace Popup -->
{#if showTrace}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="overlay" onclick={(e) => { if (e.target === e.currentTarget) closeTrace(); }}>
		<div class="trace-modal glass">
			<div class="trace-header">
				<h2 class="serif">Matching Process</h2>
				<button class="close-btn" onclick={closeTrace}>&#10005;</button>
			</div>

			<div class="trace-body">
				{#if tracePolling && !trace}
					<div class="trace-loading">
						<div class="spinner"></div>
						<p>Running matching pipeline...</p>
					</div>
				{:else if traceTimeout}
					<div class="trace-error">
						<p>Matching is taking longer than expected. Check back in the Queries tab.</p>
					</div>
				{:else if trace}
					<div class="steps">
						{#each trace.steps as step (step.step)}
							<div class="step" class:step-pass={step.status === 'pass'} class:step-fail={step.status === 'fail'}>
								<div class="step-header">
									<span class="step-icon" class:icon-pass={step.status === 'pass'} class:icon-fail={step.status === 'fail'}>
										{stepIcon(step.status)}
									</span>
									<span class="step-label">{step.label}</span>
								</div>

								{#if step.step === 'metadata' && step.status === 'pass'}
									<div class="step-detail">
										<span class="tag">Intent: {step.intent}</span>
										{#if step.category}<span class="tag">{step.category}</span>{/if}
										{#if step.complementary_intents?.length}
											<span class="tag muted">Looking for: {step.complementary_intents.join(', ')}</span>
										{/if}
									</div>

								{:else if step.step === 'candidate_search' && step.status === 'pass'}
									<div class="step-detail">
										<p class="step-summary">{step.total_found} candidate(s) found with complementary intent</p>
										{#if step.candidates?.length}
											<ul class="candidate-list">
												{#each step.candidates as c}
													<li class="candidate-item pass">
														<span class="c-icon pass-icon">✓</span>
														<span class="c-text">{c.text}</span>
														<span class="c-intent">{c.intent}</span>
													</li>
												{/each}
											</ul>
										{/if}
									</div>

								{:else if step.step === 'llm_scoring' && step.status === 'pass'}
									<div class="step-detail">
										<p class="step-summary">Threshold: {(step.threshold * 100).toFixed(0)}%</p>
										{#if step.candidates?.length}
											<ul class="candidate-list">
												{#each step.candidates as c}
													<li class="candidate-item" class:pass={c.passed} class:fail={!c.passed}>
														<span class="c-icon" class:pass-icon={c.passed} class:fail-icon={!c.passed}>
															{c.passed ? '✓' : '✗'}
														</span>
														<div class="c-body">
															<span class="c-text">{c.text}</span>
															<div class="c-meta">
																<span class="score-badge" class:score-pass={c.passed} class:score-fail={!c.passed}>
																	{(c.score * 100).toFixed(0)}% match
																</span>
																{#if c.reasoning}
																	<span class="c-reasoning">{c.reasoning}</span>
																{/if}
															</div>
														</div>
													</li>
												{/each}
											</ul>
										{/if}
									</div>

								{:else if step.step === 'matches_created'}
									<div class="step-detail">
										<p class="step-summary">{step.detail}</p>
									</div>

								{:else if step.detail}
									<div class="step-detail">
										<p class="step-summary">{step.detail}</p>
									</div>
								{/if}
							</div>
						{/each}
					</div>

					{#if matchCount() > 0}
						<div class="trace-footer">
							<button class="btn-primary btn-sm" onclick={() => { closeTrace(); goto('/queries'); }}>
								View {matchCount()} match{matchCount() > 1 ? 'es' : ''} →
							</button>
						</div>
					{/if}
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	/* ── Hero ── */
	.hero {
		min-height: calc(100vh - 64px);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 64px;
		padding: 48px 0 80px;
	}
	.hero-content {
		text-align: center;
		max-width: 640px;
	}
	.hero-title {
		font-size: clamp(2.5rem, 8vw, 5.5rem);
		font-weight: 700;
		line-height: 1.05;
		letter-spacing: -1px;
	}
	.gold-word {
		font-style: italic;
		color: var(--gold-light);
	}
	.hero-sub {
		color: var(--text-secondary);
		font-size: 18px;
		line-height: 1.6;
		margin: 24px 0 36px;
		font-weight: 300;
	}
	.hero-ctas {
		display: flex;
		gap: 12px;
		justify-content: center;
		flex-wrap: wrap;
	}
	.hero-ctas a {
		padding: 13px 28px;
		font-size: 15px;
		font-weight: 500;
		text-decoration: none;
		display: inline-block;
	}

	/* ── Diagram ── */
	.hero-diagram {
		position: relative;
		width: 700px;
		max-width: 100%;
		height: 480px;
		flex-shrink: 0;
	}
	.diagram-svg {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}
	.node-line {
		animation: pulsing-branch 3s ease-in-out infinite;
	}

	.center-card {
		position: absolute;
		left: 50%;
		top: 50%;
		transform: translate(-50%, -50%);
		width: 200px;
		height: 120px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 4px;
		box-shadow: var(--glow);
	}
	.center-card-logo {
		font-size: 28px;
		font-weight: 700;
		font-style: italic;
		color: var(--gold-light);
	}
	.center-card-label {
		font-size: 13px;
		font-weight: 600;
		color: var(--text);
	}
	.center-card-sub {
		font-size: 11px;
		color: var(--text-secondary);
	}

	.sat-card {
		position: absolute;
		width: 190px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.sat-icon {
		font-size: 18px;
		color: var(--gold);
		margin-bottom: 2px;
	}
	.sat-title {
		font-size: 13px;
		font-weight: 600;
		color: var(--text);
	}
	.sat-stat {
		font-size: 11px;
		color: var(--text-secondary);
	}
	.sat-bar {
		height: 4px;
		background: rgba(255,255,255,0.08);
		border-radius: 2px;
		overflow: hidden;
		margin-top: 2px;
	}
	.sat-bar-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--gold), var(--gold-light));
		border-radius: 2px;
	}
	.sat-score {
		font-size: 11px;
		color: var(--gold-light);
	}
	.sat-score-big {
		font-size: 32px;
		font-weight: 700;
		color: var(--gold-light);
		font-family: 'Playfair Display', Georgia, serif;
	}
	.sat-pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		font-weight: 600;
		color: var(--gold-light);
		background: rgba(167, 139, 113, 0.12);
		border: 1px solid rgba(167, 139, 113, 0.3);
		border-radius: 9999px;
		padding: 5px 12px;
		width: fit-content;
	}
	.pill-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--gold);
		animation: breathing 1.8s ease-in-out infinite;
	}
	.sat-match-text {
		font-size: 12px;
		color: var(--text-secondary);
		margin-top: 4px;
		font-style: italic;
	}

	.sat-top-left { top: 50px; left: 0; }
	.sat-right { top: 50%; right: 0; transform: translateY(-50%); }
	.sat-bottom-left { bottom: 60px; left: 20px; }

	/* ── Features ── */
	.features {
		padding: 80px 0;
	}
	.features-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 24px;
	}
	@media (max-width: 900px) {
		.features-grid { grid-template-columns: repeat(2, 1fr); }
		.hero-diagram { width: 100%; height: 340px; }
		.sat-top-left { top: 20px; left: 0; width: 140px; }
		.sat-right { right: 0; width: 140px; }
		.sat-bottom-left { bottom: 20px; left: 0; width: 140px; }
		.center-card { width: 150px; height: 90px; }
	}
	@media (max-width: 600px) {
		.features-grid { grid-template-columns: 1fr; }
	}
	.feature-card {
		padding: 28px 24px;
		transition: border-color 0.2s ease, transform 0.2s ease;
	}
	.feature-card:hover {
		border-color: rgba(255, 255, 255, 0.2);
	}
	.feature-card:hover .feature-icon {
		transform: scale(1.1);
	}
	.feature-icon {
		width: 48px;
		height: 48px;
		background: rgba(167, 139, 113, 0.1);
		border-radius: var(--radius-sm);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--gold-light);
		margin-bottom: 16px;
		transition: transform 0.2s ease;
	}
	.feature-card h3 {
		font-size: 18px;
		font-weight: 700;
		margin-bottom: 8px;
		color: var(--text);
	}
	.feature-card p {
		font-size: 14px;
		color: var(--text-secondary);
		line-height: 1.6;
	}

	/* ── Footer ── */
	.site-footer {
		border-top: 1px solid var(--border);
		padding: 60px 0 32px;
		margin-top: 40px;
	}
	.footer-inner {
		display: grid;
		grid-template-columns: 2fr 1fr 2fr;
		gap: 40px;
		margin-bottom: 40px;
	}
	@media (max-width: 700px) {
		.footer-inner { grid-template-columns: 1fr; }
	}
	.footer-logo {
		font-size: 20px;
		font-weight: 700;
		font-style: italic;
		color: var(--text);
		display: block;
		margin-bottom: 8px;
	}
	.footer-tagline {
		font-size: 13px;
		color: var(--text-secondary);
		line-height: 1.5;
	}
	.footer-col {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.footer-col a {
		font-size: 13px;
		color: var(--text-secondary);
		text-decoration: none;
		transition: color 0.15s ease;
	}
	.footer-col a:hover {
		color: var(--gold-light);
	}
	.footer-label {
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--text-secondary);
		margin-bottom: 4px;
	}
	.footer-input-row {
		display: flex;
		gap: 8px;
	}
	.footer-input-row input {
		flex: 1;
		border-radius: 9999px;
		padding: 9px 16px;
		font-size: 13px;
	}
	.footer-submit {
		width: 36px;
		height: 36px;
		border-radius: 50%;
		padding: 0;
		font-size: 18px;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.footer-bottom {
		border-top: 1px solid var(--border);
		padding-top: 24px;
		font-size: 12px;
		color: var(--text-secondary);
	}

	/* ── Logged in chat ── */
	.page-header { margin-bottom: 24px; }
	.page-header h1 {
		font-size: 28px;
		font-weight: 700;
		letter-spacing: -0.3px;
	}
	.page-header p {
		color: var(--text-secondary);
		font-size: 14px;
		margin-top: 4px;
	}

	.chat-panel {
		overflow: hidden;
	}
	.chat-messages {
		height: 420px;
		overflow-y: auto;
		padding: 24px;
		display: flex;
		flex-direction: column;
		gap: 12px;
		background: rgba(0, 0, 0, 0.2);
	}
	.msg { display: flex; }
	.msg-user { justify-content: flex-end; }
	.msg-bubble {
		max-width: 75%;
		padding: 10px 16px;
		border-radius: 18px;
		font-size: 14px;
		line-height: 1.45;
		background: rgba(255, 255, 255, 0.06);
		color: var(--text);
		border: 1px solid var(--glass-border);
	}
	.bubble-user {
		background: rgba(167, 139, 113, 0.15);
		border-color: rgba(167, 139, 113, 0.3);
		color: var(--gold-hover);
	}
	.typing { display: flex; gap: 4px; padding: 12px 18px; }
	.dot {
		width: 6px;
		height: 6px;
		background: var(--text-secondary);
		border-radius: 50%;
		animation: bounce 1.2s infinite;
	}
	.dot:nth-child(2) { animation-delay: 0.15s; }
	.dot:nth-child(3) { animation-delay: 0.3s; }

	.chat-input {
		display: flex;
		gap: 8px;
		padding: 16px 20px;
		border-top: 1px solid var(--glass-border);
		background: rgba(255, 255, 255, 0.02);
	}
	.chat-input input {
		flex: 1;
		border-radius: 9999px;
		padding: 10px 18px;
		background: rgba(255, 255, 255, 0.04);
	}
	.send-btn { border-radius: 9999px; padding: 10px 24px; }

	.success-bar {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 14px 20px;
		background: rgba(74, 222, 128, 0.06);
		border-top: 1px solid rgba(74, 222, 128, 0.2);
		flex-wrap: wrap;
	}
	.success-icon {
		width: 24px;
		height: 24px;
		background: rgba(74, 222, 128, 0.2);
		color: var(--green);
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 13px;
		font-weight: 700;
		flex-shrink: 0;
	}
	.success-bar span { flex: 1; font-size: 14px; font-weight: 500; color: var(--text); }
	.success-actions { display: flex; gap: 8px; flex-shrink: 0; flex-wrap: wrap; }

	/* Overlay */
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.7);
		z-index: 200;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 24px;
	}
	.trace-modal {
		width: 100%;
		max-width: 560px;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		box-shadow: var(--glow), var(--shadow-lg);
	}
	.trace-header {
		padding: 20px 24px 16px;
		border-bottom: 1px solid var(--glass-border);
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.trace-header h2 {
		font-size: 18px;
		font-weight: 700;
		font-style: italic;
		color: var(--gold-light);
	}
	.close-btn {
		background: none;
		color: var(--text-secondary);
		font-size: 14px;
		padding: 4px 8px;
		border-radius: var(--radius-sm);
	}
	.close-btn:hover {
		color: var(--text);
		background: rgba(255,255,255,0.06);
	}

	.trace-body {
		flex: 1;
		overflow-y: auto;
		padding: 16px 24px;
	}
	.trace-loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		padding: 40px 0;
		color: var(--text-secondary);
		font-size: 14px;
	}
	.spinner {
		width: 28px;
		height: 28px;
		border: 2px solid rgba(255,255,255,0.1);
		border-top-color: var(--gold);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	.trace-error { padding: 20px 0; color: var(--text-secondary); font-size: 14px; text-align: center; }

	.steps { display: flex; flex-direction: column; gap: 2px; }
	.step { border-radius: var(--radius-sm); overflow: hidden; }
	.step-header {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 12px;
	}
	.step-icon {
		width: 20px;
		height: 20px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 11px;
		font-weight: 700;
		flex-shrink: 0;
	}
	.icon-pass { background: rgba(74,222,128,0.2); color: var(--green); border: 1px solid rgba(74,222,128,0.4); }
	.icon-fail { background: rgba(248,113,113,0.2); color: var(--red); border: 1px solid rgba(248,113,113,0.4); }
	.step-label { font-size: 14px; font-weight: 600; color: var(--text); }

	.step-detail { padding: 0 12px 12px 42px; }
	.step-summary { font-size: 13px; color: var(--text-secondary); margin: 0 0 8px; }

	.tag {
		display: inline-block;
		font-size: 12px;
		padding: 2px 8px;
		border-radius: 4px;
		background: rgba(255,255,255,0.06);
		color: var(--text-secondary);
		margin: 0 4px 4px 0;
	}
	.tag.muted { color: rgba(156,163,175,0.6); }

	.candidate-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
	.candidate-item {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 8px 10px;
		border-radius: var(--radius-sm);
		background: rgba(255,255,255,0.03);
		border: 1px solid var(--glass-border);
		font-size: 13px;
	}
	.c-icon {
		width: 18px;
		height: 18px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10px;
		font-weight: 700;
		flex-shrink: 0;
		margin-top: 1px;
	}
	.pass-icon { background: rgba(74,222,128,0.2); color: var(--green); }
	.fail-icon { background: rgba(248,113,113,0.2); color: var(--red); }
	.c-body { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0; }
	.c-text { color: var(--text); line-height: 1.4; }
	.c-intent {
		margin-left: auto;
		flex-shrink: 0;
		font-size: 11px;
		text-transform: uppercase;
		font-weight: 600;
		color: var(--text-secondary);
		padding: 1px 6px;
		border-radius: 3px;
		background: rgba(255,255,255,0.06);
	}
	.c-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
	.score-badge {
		font-size: 11px;
		font-weight: 700;
		padding: 2px 8px;
		border-radius: 10px;
		flex-shrink: 0;
	}
	.score-pass { background: rgba(74,222,128,0.15); color: var(--green); }
	.score-fail { background: rgba(248,113,113,0.15); color: var(--red); }
	.c-reasoning { font-size: 12px; color: var(--text-secondary); }

	.trace-footer {
		padding: 12px 0 4px;
		border-top: 1px solid var(--glass-border);
		margin-top: 12px;
		display: flex;
		justify-content: flex-end;
	}
</style>

<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';

	let queries = $state<any[]>([]);
	let matches = $state<any[]>([]);
	let loading = $state(true);
	let expandedQuery = $state<string | null>(null);
	let tab = $state<'open' | 'closed'>('open');

	onMount(loadData);

	async function loadData() {
		loading = true;
		try {
			[queries, matches] = await Promise.all([api.listQueries(), api.listMatches()]);
		} catch { /* not logged in */ }
		finally { loading = false; }
	}

	function matchesForQuery(queryId: string) {
		return matches.filter((m: any) => m.match_queries.some((mq: any) => mq.query.id === queryId));
	}

	function otherQueries(match: any, myQueryId: string) {
		return match.match_queries.filter((mq: any) => mq.query.id !== myQueryId).map((mq: any) => mq.query);
	}

	async function deleteQuery(id: string) {
		await api.deleteQuery(id);
		queries = queries.filter(q => q.id !== id);
	}

	async function accept(matchId: string) {
		matches = matches.map(m => m.id === matchId ? { ...m, _loading: true } : m);
		const updated = await api.acceptMatch(matchId);
		matches = matches.map(m => m.id === matchId ? updated : m);
	}

	async function reject(matchId: string) {
		const updated = await api.rejectMatch(matchId);
		matches = matches.map(m => m.id === matchId ? updated : m);
	}

	function toggle(id: string) {
		expandedQuery = expandedQuery === id ? null : id;
	}

	function timeAgo(dateStr: string) {
		const diff = Date.now() - new Date(dateStr).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins}m ago`;
		const hours = Math.floor(mins / 60);
		if (hours < 24) return `${hours}h ago`;
		return `${Math.floor(hours / 24)}d ago`;
	}

	function filteredQueries() {
		return queries.filter(q => tab === 'open' ? q.status === 'active' : q.status === 'cancelled');
	}
</script>

<div class="page-header">
	<h1 class="serif">My queries</h1>
	<a href="/" class="btn-primary btn-sm">New query</a>
</div>

{#if loading}
	<div class="empty-state glass"><p>Loading...</p></div>
{:else if queries.length === 0}
	<div class="empty-state glass">
		<p class="empty-title">No queries yet</p>
		<p class="empty-desc">Create a query to get matched with the right people.</p>
		<a href="/" class="btn-primary" style="margin-top:16px;display:inline-block;text-decoration:none;padding:10px 24px">Create query</a>
	</div>
{:else}
	<div class="tabs">
		<button class="tab" class:active={tab === 'open'} onclick={() => tab = 'open'}>
			Open
			{#if queries.filter(q => q.status === 'active').length > 0}
				<span class="tab-count">{queries.filter(q => q.status === 'active').length}</span>
			{/if}
		</button>
		<button class="tab" class:active={tab === 'closed'} onclick={() => tab = 'closed'}>
			Closed
			{#if queries.filter(q => q.status === 'cancelled').length > 0}
				<span class="tab-count">{queries.filter(q => q.status === 'cancelled').length}</span>
			{/if}
		</button>
	</div>

	{#if filteredQueries().length === 0}
		<div class="empty-state glass" style="margin-top: 24px;">
			<p class="empty-title">{tab === 'open' ? 'No open queries' : 'No closed queries'}</p>
		</div>
	{:else}
		<div class="query-list">
			{#each filteredQueries() as q (q.id)}
			{@const qMatches = matchesForQuery(q.id)}
			<div class="query-card glass" class:expanded={expandedQuery === q.id}>
				<button class="query-row" onclick={() => toggle(q.id)}>
					<div class="query-left">
						<span class="intent">{q.intent || 'processing'}</span>
						<span class="query-text">{q.raw_text}</span>
					</div>
					<div class="query-right">
						{#if qMatches.length > 0}
							<span class="badge">{qMatches.length}</span>
						{/if}
						<span class="status" class:active={q.status === 'active'}>{q.status}</span>
						<span class="chevron" class:open={expandedQuery === q.id}>&#9662;</span>
					</div>
				</button>

				{#if expandedQuery === q.id}
					<div class="query-body">
						<div class="meta-row">
							{#if q.category}<span class="meta-tag">{q.category}</span>{/if}
							{#if q.group_size > 2}<span class="meta-tag">Group of {q.group_size}</span>{/if}
							<span class="time">{timeAgo(q.created_at)}</span>
						</div>

						{#if qMatches.length > 0}
							<div class="matches-section">
								<h3>Matches</h3>
								{#each qMatches as m (m.id)}
									<div class="match-card">
										<div class="match-header">
											<div class="score-bar-wrap">
												<div class="score-label">{(m.compatibility_score * 100).toFixed(0)}% match</div>
												<div class="score-bar">
													<div class="score-fill" style="width: {(m.compatibility_score * 100).toFixed(0)}%"></div>
												</div>
											</div>
											<span class="match-status" class:s-pending={m.status==='pending'} class:s-accepted={m.status==='accepted'} class:s-rejected={m.status==='rejected'}>
												{m.status}
											</span>
										</div>
										{#each otherQueries(m, q.id) as oq}
											<p class="match-query-text">{oq.raw_text}</p>
										{/each}
										{#if m.reasoning}
											<p class="match-reasoning">{m.reasoning}</p>
										{/if}
										<div class="match-actions">
											{#if m.status === 'pending'}
												<button class="btn-success btn-sm" onclick={() => accept(m.id)}>Accept</button>
												<button class="btn-danger btn-sm" onclick={() => reject(m.id)}>Decline</button>
											{/if}
											{#if m.status === 'accepted' && m.chatroom_id}
												<a href="/chat/{m.chatroom_id}" class="btn-gold btn-sm msg-btn">Message</a>
											{/if}
										</div>
									</div>
								{/each}
							</div>
						{:else}
							<p class="no-matches">No matches yet. We'll keep looking.</p>
						{/if}

						{#if q.status === 'active'}
							<div class="danger-zone">
								<button class="btn-danger btn-sm" onclick={() => deleteQuery(q.id)}>Delete query</button>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
		</div>
	{/if}
{/if}

<style>
	.page-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 28px;
	}
	.page-header h1 {
		font-size: 28px;
		font-weight: 700;
		font-style: italic;
		color: var(--gold-light);
	}

	.tabs {
		display: flex;
		gap: 4px;
		margin-bottom: 20px;
		border-bottom: 1px solid var(--glass-border);
		padding-bottom: 0;
	}
	.tab {
		padding: 10px 18px;
		background: none;
		border: none;
		font-size: 13px;
		font-weight: 500;
		letter-spacing: 0.05em;
		color: var(--text-secondary);
		cursor: pointer;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
		display: flex;
		align-items: center;
		gap: 8px;
		transition: color 0.15s ease;
		border-radius: 0;
	}
	.tab.active {
		color: var(--gold-light);
		border-bottom-color: var(--gold);
	}
	.tab-count {
		background: rgba(167, 139, 113, 0.15);
		color: var(--gold-light);
		padding: 2px 8px;
		border-radius: 12px;
		font-size: 11px;
		font-weight: 700;
	}

	.empty-state {
		text-align: center;
		padding: 60px 20px;
	}
	.empty-title { font-size: 17px; font-weight: 600; }
	.empty-desc { color: var(--text-secondary); font-size: 14px; margin-top: 6px; }

	.query-list { display: flex; flex-direction: column; gap: 8px; }

	.query-card {
		overflow: hidden;
		transition: border-color 0.15s ease;
	}
	.query-card.expanded {
		border-color: rgba(255, 255, 255, 0.18);
	}

	.query-row {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		background: transparent;
		text-align: left;
		gap: 12px;
		border-radius: var(--radius);
		transition: background 0.1s ease;
	}
	.query-row:hover { background: rgba(255,255,255,0.03); }
	.query-left {
		display: flex;
		align-items: center;
		gap: 12px;
		flex: 1;
		min-width: 0;
	}
	.intent {
		font-size: 11px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		padding: 3px 10px;
		border-radius: 9999px;
		background: rgba(167, 139, 113, 0.12);
		color: var(--gold-light);
		border: 1px solid rgba(167, 139, 113, 0.25);
		flex-shrink: 0;
	}
	.query-text {
		font-size: 14px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: var(--text);
	}
	.query-right {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-shrink: 0;
	}
	.badge {
		background: var(--gold);
		color: #000;
		font-size: 11px;
		font-weight: 700;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.status { font-size: 12px; color: var(--text-secondary); }
	.status.active { color: var(--green); font-weight: 500; }
	.chevron {
		font-size: 11px;
		color: var(--text-secondary);
		transition: transform 0.15s ease;
	}
	.chevron.open { transform: rotate(180deg); }

	.query-body {
		padding: 0 20px 20px;
		border-top: 1px solid var(--glass-border);
	}
	.meta-row {
		display: flex;
		align-items: center;
		gap: 8px;
		padding-top: 14px;
		flex-wrap: wrap;
	}
	.meta-tag {
		font-size: 12px;
		padding: 2px 10px;
		border-radius: 4px;
		background: rgba(255,255,255,0.05);
		color: var(--text-secondary);
		border: 1px solid var(--glass-border);
	}
	.time { font-size: 12px; color: rgba(156,163,175,0.5); }

	.matches-section { margin-top: 18px; }
	.matches-section h3 {
		font-size: 11px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--text-secondary);
		margin-bottom: 12px;
	}

	.match-card {
		padding: 16px;
		background: rgba(255,255,255,0.02);
		border: 1px solid var(--glass-border);
		border-radius: var(--radius-sm);
		margin-bottom: 8px;
	}
	.match-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10px;
		gap: 16px;
	}
	.score-bar-wrap {
		flex: 1;
		min-width: 0;
	}
	.score-label {
		font-size: 12px;
		font-weight: 700;
		color: var(--gold-light);
		margin-bottom: 4px;
	}
	.score-bar {
		height: 4px;
		background: rgba(255,255,255,0.06);
		border-radius: 2px;
		overflow: hidden;
	}
	.score-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--gold), var(--gold-light));
		border-radius: 2px;
		transition: width 0.5s ease;
	}
	.match-status { font-size: 11px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em; flex-shrink: 0; }
	.s-pending { color: var(--text-secondary); }
	.s-accepted { color: var(--green); }
	.s-rejected { color: var(--red); }
	.match-query-text { font-size: 14px; line-height: 1.5; color: var(--text); }
	.match-reasoning { font-size: 13px; color: var(--text-secondary); margin-top: 6px; line-height: 1.4; }
	.match-actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
	.msg-btn { display: inline-block; text-decoration: none; }

	.no-matches { font-size: 13px; color: rgba(156,163,175,0.5); margin-top: 14px; }
	.danger-zone { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--glass-border); }
</style>

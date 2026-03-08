<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';

	let chatrooms = $state<any[]>([]);
	let loading = $state(true);

	onMount(async () => {
		try {
			chatrooms = await api.listChatrooms();
		} catch { /* not logged in */ }
		finally { loading = false; }
	});

	function timeAgo(dateStr: string) {
		const diff = Date.now() - new Date(dateStr).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins}m ago`;
		const hours = Math.floor(mins / 60);
		if (hours < 24) return `${hours}h ago`;
		return `${Math.floor(hours / 24)}d ago`;
	}
</script>

<div class="page-header">
	<h1 class="serif">Messages</h1>
</div>

{#if loading}
	<div class="empty-state glass"><p>Loading...</p></div>
{:else if chatrooms.length === 0}
	<div class="empty-state glass">
		<p class="empty-title">No messages yet</p>
		<p class="empty-desc">Accept a match to start a conversation.</p>
	</div>
{:else}
	<div class="room-list">
		{#each chatrooms as room (room.id)}
			<a href="/chat/{room.id}" class="room-row glass">
				<div class="room-avatar">{room.name.charAt(0).toUpperCase()}</div>
				<div class="room-info">
					<span class="room-name">{room.name}</span>
					<span class="room-time">{timeAgo(room.created_at)}</span>
				</div>
				<span class="room-arrow">&#8250;</span>
			</a>
		{/each}
	</div>
{/if}

<style>
	.page-header { margin-bottom: 28px; }
	.page-header h1 {
		font-size: 28px;
		font-weight: 700;
		font-style: italic;
		color: var(--gold-light);
	}

	.empty-state {
		text-align: center;
		padding: 60px 20px;
	}
	.empty-title { font-size: 17px; font-weight: 600; }
	.empty-desc { color: var(--text-secondary); font-size: 14px; margin-top: 6px; }

	.room-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.room-row {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 18px 22px;
		text-decoration: none;
		color: var(--text);
		transition: border-color 0.15s ease, transform 0.15s ease;
	}
	.room-row:hover {
		border-color: rgba(255, 255, 255, 0.2);
		transform: translateY(-1px);
		color: var(--text);
	}

	.room-avatar {
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: rgba(167, 139, 113, 0.2);
		border: 1px solid rgba(167, 139, 113, 0.3);
		color: var(--gold-light);
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 16px;
		font-family: 'Playfair Display', Georgia, serif;
		flex-shrink: 0;
	}
	.room-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.room-name {
		font-size: 15px;
		font-weight: 500;
		color: var(--text);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.room-time { font-size: 12px; color: var(--text-secondary); margin-top: 3px; }
	.room-arrow { color: var(--text-secondary); font-size: 22px; flex-shrink: 0; }
</style>

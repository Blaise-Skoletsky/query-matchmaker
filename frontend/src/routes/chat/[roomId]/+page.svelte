<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { page } from '$app/stores';
	import { api } from '$lib/api';
	import { createChatSocket } from '$lib/ws';
	import { user } from '$lib/stores/auth';

	let messages = $state<any[]>([]);
	let input = $state('');
	let socket: ReturnType<typeof createChatSocket> | null = null;
	let messagesEl: HTMLDivElement;
	let roomInfo = $state<{ name: string; members: { user_id: string; display_name: string }[] } | null>(null);

	const roomId = $derived($page.params.roomId);

	onMount(async () => {
		const [msgs, info] = await Promise.all([
			api.getMessages(roomId),
			api.getChatroom(roomId),
		]);
		messages = msgs;
		roomInfo = info;
		await scrollToBottom();

		socket = createChatSocket(roomId, async (msg) => {
			// Replace optimistic (pending) message with server-confirmed one
			const pendingIdx = messages.findIndex(
				m => m.id?.startsWith('pending-') &&
					m.user_id === msg.user_id &&
					m.content === msg.content
			);
			if (pendingIdx !== -1) {
				messages[pendingIdx] = msg;
				messages = messages;
			} else if (!messages.some(m => m.id === msg.id)) {
				messages = [...messages, msg];
			}
			await scrollToBottom();
		});
	});

	onDestroy(() => { socket?.close(); });

	async function scrollToBottom() {
		await tick();
		if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
	}

	async function send() {
		const text = input.trim();
		if (!text || !socket || !$user) return;
		input = '';

		const optimisticMsg = {
			id: `pending-${Date.now()}`,
			content: text,
			user_id: $user.id,
			user_display_name: $user.display_name,
			chatroom_id: roomId,
			created_at: new Date().toISOString(),
		};
		messages = [...messages, optimisticMsg];
		await scrollToBottom();

		socket.send(text);
	}

	function otherMembers() {
		if (!roomInfo || !$user) return [];
		return roomInfo.members.filter(m => m.user_id !== $user!.id);
	}
</script>

<div class="chat-page glass">
	<div class="chat-topbar">
		<a href="/messages" class="back-btn">&#8249; Messages</a>
		{#if roomInfo}
			<div class="room-info">
				<span class="room-name">{roomInfo.name}</span>
				<span class="room-members">
					with {otherMembers().map(m => m.display_name).join(', ') || 'no one else yet'}
				</span>
			</div>
		{/if}
	</div>

	<div class="chat-messages" bind:this={messagesEl}>
		{#if messages.length === 0}
			<div class="empty-chat">
				<p>No messages yet. Say hello!</p>
			</div>
		{/if}
		{#each messages as msg (msg.id)}
			<div class="msg" class:msg-own={msg.user_id === $user?.id}>
				<div class="msg-bubble" class:own={msg.user_id === $user?.id}>
					{#if msg.user_id !== $user?.id}
						<span class="sender">{msg.user_display_name}</span>
					{/if}
					<p>{msg.content}</p>
					<span class="msg-time">{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
				</div>
			</div>
		{/each}
	</div>

	<form class="chat-input" onsubmit={(e) => { e.preventDefault(); send(); }}>
		<input type="text" bind:value={input} placeholder="Type a message..." />
		<button class="btn-gold send-btn" type="submit" disabled={!input.trim()}>Send</button>
	</form>
</div>

<style>
	.chat-page {
		display: flex;
		flex-direction: column;
		height: calc(100vh - 140px);
		overflow: hidden;
	}
	.chat-topbar {
		padding: 14px 22px;
		border-bottom: 1px solid var(--glass-border);
		display: flex;
		align-items: center;
		gap: 18px;
		background: rgba(255,255,255,0.02);
		flex-shrink: 0;
	}
	.back-btn {
		font-size: 14px;
		color: var(--text-secondary);
		text-decoration: none;
		font-weight: 500;
		flex-shrink: 0;
		transition: color 0.15s ease;
	}
	.back-btn:hover { color: var(--gold-light); }
	.room-info {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.room-name {
		font-size: 15px;
		font-weight: 600;
		color: var(--text);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		font-family: 'Playfair Display', Georgia, serif;
		font-style: italic;
	}
	.room-members {
		font-size: 12px;
		color: var(--text-secondary);
		margin-top: 1px;
	}

	.chat-messages {
		flex: 1;
		overflow-y: auto;
		padding: 24px;
		display: flex;
		flex-direction: column;
		gap: 10px;
		background: rgba(0, 0, 0, 0.2);
	}
	.empty-chat {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.empty-chat p {
		font-size: 14px;
		color: var(--text-secondary);
	}

	/* Own = right-aligned (current user), other = left-aligned */
	.msg { display: flex; justify-content: flex-start; }
	.msg-own { justify-content: flex-end; }

	.msg-bubble {
		max-width: 70%;
		padding: 10px 16px;
		border-radius: 18px;
		background: rgba(255,255,255,0.05);
		border: 1px solid var(--glass-border);
		font-size: 14px;
		line-height: 1.45;
		color: var(--text);
	}
	.msg-bubble.own {
		background: rgba(167, 139, 113, 0.12);
		border-color: rgba(167, 139, 113, 0.25);
		color: var(--gold-hover);
	}
	.sender {
		font-size: 11px;
		font-weight: 700;
		color: var(--gold-light);
		display: block;
		margin-bottom: 4px;
		letter-spacing: 0.04em;
	}
	.msg-bubble p { margin: 0; }
	.msg-time {
		font-size: 10px;
		color: var(--text-secondary);
		display: block;
		margin-top: 5px;
	}
	.own .msg-time { color: rgba(201, 184, 160, 0.5); }

	.chat-input {
		display: flex;
		gap: 10px;
		padding: 16px 20px;
		border-top: 1px solid var(--glass-border);
		background: rgba(255,255,255,0.02);
		flex-shrink: 0;
	}
	.chat-input input {
		flex: 1;
		border-radius: 9999px;
		padding: 11px 20px;
		background: rgba(255,255,255,0.04);
	}
	.send-btn {
		border-radius: 9999px;
		padding: 10px 26px;
		font-weight: 600;
	}
</style>

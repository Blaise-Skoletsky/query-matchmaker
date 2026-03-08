<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { loadUser, isLoggedIn, authLoaded, user, logout } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const PROTECTED = ['/queries', '/messages', '/chat'];

	onMount(async () => {
		await loadUser();
	});

	$effect(() => {
		if ($authLoaded && !$isLoggedIn) {
			const path = $page.url.pathname;
			if (PROTECTED.some(p => path.startsWith(p))) {
				goto('/login');
			}
		}
	});

	function handleLogout() {
		logout();
		goto('/login');
	}

	function isActive(path: string): boolean {
		return $page.url.pathname === path;
	}
</script>

<div class="shell">
	<nav class="glass">
		<div class="nav-inner">
			<a href="/" class="logo serif">MatchMaker</a>
			{#if $isLoggedIn}
				<div class="nav-tabs">
					<a href="/" class="tab" class:active={isActive('/')}>Create</a>
					<a href="/queries" class="tab" class:active={isActive('/queries')}>Queries</a>
					<a href="/messages" class="tab" class:active={isActive('/messages')}>Messages</a>
				</div>
				<div class="nav-right">
					<span class="user-name">{$user?.display_name}</span>
					<button class="btn-logout" onclick={handleLogout}>Log out</button>
				</div>
			{:else}
				<div class="nav-right">
					<a href="/login" class="btn-outline btn-sm">Log in</a>
					<a href="/login" class="btn-primary btn-sm">Start Free Trial</a>
				</div>
			{/if}
		</div>
	</nav>

	<main>
		{@render children()}
	</main>
</div>

<style>
	.shell {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
	}
	nav {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 100;
		border-radius: 0;
		border-top: none;
		border-left: none;
		border-right: none;
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
		background: rgba(10, 10, 10, 0.8);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
	}
	.nav-inner {
		max-width: 1200px;
		margin: 0 auto;
		padding: 0 32px;
		height: 64px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 32px;
	}
	.logo {
		font-size: 22px;
		font-weight: 700;
		font-style: italic;
		color: var(--text);
		text-decoration: none;
		flex-shrink: 0;
		letter-spacing: -0.3px;
	}
	.logo:hover { color: var(--gold-light); }
	.nav-tabs {
		display: flex;
		gap: 4px;
	}
	.tab {
		padding: 7px 16px;
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--text-secondary);
		text-decoration: none;
		border-radius: 9999px;
		transition: all 0.15s ease;
	}
	.tab:hover {
		color: var(--text);
		background: rgba(255, 255, 255, 0.06);
	}
	.tab.active {
		color: var(--gold-light);
		background: rgba(167, 139, 113, 0.12);
	}
	.nav-right {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-shrink: 0;
	}
	.user-name {
		font-size: 13px;
		color: var(--text-secondary);
	}
	.btn-logout {
		background: transparent;
		color: var(--text-secondary);
		font-size: 11px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		padding: 6px 14px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 9999px;
	}
	.btn-logout:hover {
		color: var(--text);
		border-color: rgba(255, 255, 255, 0.25);
		background: rgba(255, 255, 255, 0.04);
	}
	main {
		flex: 1;
		max-width: 1200px;
		width: 100%;
		margin: 0 auto;
		padding: 96px 32px 48px;
		position: relative;
		z-index: 1;
	}
</style>

type MessageHandler = (msg: any) => void;

export function createChatSocket(roomId: string, onMessage: MessageHandler): { send: (content: string) => void; close: () => void } {
	const token = sessionStorage.getItem('token');
	const ws = new WebSocket(`ws://localhost:8000/ws/chat/${roomId}?token=${token}`);

	ws.onmessage = (event) => {
		const data = JSON.parse(event.data);
		onMessage(data);
	};

	ws.onerror = (e) => console.error('WebSocket error:', e);

	return {
		send(content: string) {
			if (ws.readyState === WebSocket.OPEN) {
				ws.send(JSON.stringify({ content }));
			}
		},
		close() {
			ws.close();
		}
	};
}

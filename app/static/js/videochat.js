(function() {
    var container = document.getElementById('videochat-container');
    if (!container) return;

    var socket = io();
    var roomId = container.dataset.roomId;
    var myUserId = parseInt(container.dataset.myUserId, 10);
    var myUserName = container.dataset.myUserName;
    var otherUserId = parseInt(container.dataset.otherUserId, 10);
    var otherUserName = container.dataset.otherUserName;
    var redirectUrl = container.dataset.redirectUrl;
    var isIncoming = container.dataset.incoming === '1' ||
        new URLSearchParams(window.location.search).get('incoming') === '1';

    var localVideo = document.getElementById('local-video');
    var remoteVideo = document.getElementById('remote-video');
    var remotePlaceholder = document.getElementById('remote-placeholder');
    var statusEl = document.getElementById('call-status');
    var toggleVideoBtn = document.getElementById('toggle-video');
    var toggleAudioBtn = document.getElementById('toggle-audio');
    var endCallBtn = document.getElementById('end-call');

    var localStream = null;
    var peerConnection = null;
    var videoEnabled = true;
    var audioEnabled = true;
    var mediaReady = false;
    var makingOffer = false;

    var config = {
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' }
        ]
    };

    function updateStatus(text, className) {
        statusEl.textContent = text;
        statusEl.className = 'call-status ' + (className || '');
    }

    function mediaErrorMessage(err) {
        if (!err) return 'Could not access camera or microphone.';
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            return 'Camera/microphone blocked. Allow access in the browser address bar and try again.';
        }
        if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
            return 'No camera or microphone found on this device.';
        }
        if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
            return 'Camera is busy (another tab or app may be using it). Close other call windows or use another browser.';
        }
        if (err.name === 'OverconstrainedError') {
            return 'Camera does not support the requested settings. Try another device.';
        }
        if (err.name === 'SecurityError') {
            return 'Camera requires HTTPS or localhost. Open the site via http://127.0.0.1 or https.';
        }
        return 'Could not access camera or microphone: ' + (err.message || err.name || 'unknown error');
    }

    async function acquireLocalMedia() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('getUserMedia is not supported in this browser');
        }
        var attempts = [
            { video: true, audio: true },
            { video: { facingMode: 'user' }, audio: true },
            { video: true, audio: false },
            { video: false, audio: true }
        ];
        var lastErr = null;
        for (var i = 0; i < attempts.length; i++) {
            try {
                return await navigator.mediaDevices.getUserMedia(attempts[i]);
            } catch (err) {
                lastErr = err;
                console.warn('getUserMedia attempt failed:', attempts[i], err);
                if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    throw err;
                }
            }
        }
        throw lastErr || new Error('getUserMedia failed');
    }

    function ensureLocalStream() {
        if (!localStream) {
            throw new Error('Local media not ready');
        }
    }

    function createPeerConnection() {
        if (peerConnection) {
            return peerConnection;
        }
        ensureLocalStream();
        peerConnection = new RTCPeerConnection(config);
        localStream.getTracks().forEach(function(track) {
            peerConnection.addTrack(track, localStream);
        });
        peerConnection.ontrack = function(event) {
            if (event.streams && event.streams[0]) {
                remoteVideo.srcObject = event.streams[0];
                remotePlaceholder.style.display = 'none';
                updateStatus('Connected', 'connected');
            }
        };
        peerConnection.onicecandidate = function(event) {
            if (event.candidate) {
                socket.emit('ice_candidate', { room: roomId, candidate: event.candidate });
            }
        };
        peerConnection.onconnectionstatechange = function() {
            if (!peerConnection) return;
            if (peerConnection.connectionState === 'disconnected' || peerConnection.connectionState === 'failed') {
                updateStatus('Connection lost', 'error');
            }
        };
        return peerConnection;
    }

    async function startCall() {
        try {
            updateStatus('Requesting camera and microphone...');
            localStream = await acquireLocalMedia();
            mediaReady = true;
            localVideo.srcObject = localStream;
            videoEnabled = localStream.getVideoTracks().length > 0;
            audioEnabled = localStream.getAudioTracks().length > 0;
            if (!videoEnabled) {
                updateStatus('Microphone only (no camera)', '');
            }
            socket.emit('join_call', { room: roomId, user_id: myUserId });
            if (isIncoming) {
                updateStatus('Waiting for ' + otherUserName + ' to connect...');
            } else {
                socket.emit('call_request', {
                    target_user_id: otherUserId,
                    caller_id: myUserId,
                    caller_name: myUserName,
                    room: roomId
                });
                updateStatus('Calling ' + otherUserName + '...');
            }
        } catch (err) {
            mediaReady = false;
            updateStatus(mediaErrorMessage(err), 'error');
            console.error('Media error:', err);
        }
    }

    socket.on('user_joined', async function() {
        if (isIncoming || !mediaReady) return;
        try {
            updateStatus('User joined, connecting...');
            makingOffer = true;
            createPeerConnection();
            var offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);
            socket.emit('offer', { room: roomId, offer: offer });
            makingOffer = false;
        } catch (err) {
            makingOffer = false;
            console.error('Offer error:', err);
            updateStatus('Could not start connection', 'error');
        }
    });

    socket.on('offer', async function(data) {
        if (!mediaReady || !data || !data.offer) return;
        try {
            if (!isIncoming && makingOffer) return;
            createPeerConnection();
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
            var answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            socket.emit('answer', { room: roomId, answer: answer });
            updateStatus('Connecting...', '');
        } catch (err) {
            console.error('Answer error:', err);
            updateStatus('Could not connect to caller', 'error');
        }
    });

    socket.on('answer', async function(data) {
        if (!peerConnection || !data || !data.answer) return;
        try {
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
        } catch (err) {
            console.error('Remote description error:', err);
        }
    });

    socket.on('ice_candidate', async function(data) {
        if (peerConnection && data && data.candidate) {
            try {
                await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            } catch (e) {
                console.error('ICE error:', e);
            }
        }
    });

    socket.on('user_left', function() {
        updateStatus('User left the call', 'error');
        endCall(false);
    });

    socket.on('call_ended', function() {
        updateStatus('Call ended', '');
        endCall(false);
    });

    socket.on('call_declined', function() {
        updateStatus('Call declined', 'error');
    });

    toggleVideoBtn.addEventListener('click', function() {
        if (!localStream) return;
        videoEnabled = !videoEnabled;
        localStream.getVideoTracks().forEach(function(track) {
            track.enabled = videoEnabled;
        });
        toggleVideoBtn.classList.toggle('active', !videoEnabled);
    });

    toggleAudioBtn.addEventListener('click', function() {
        if (!localStream) return;
        audioEnabled = !audioEnabled;
        localStream.getAudioTracks().forEach(function(track) {
            track.enabled = audioEnabled;
        });
        toggleAudioBtn.classList.toggle('active', !audioEnabled);
    });

    function endCall(notify) {
        if (peerConnection) {
            peerConnection.close();
            peerConnection = null;
        }
        if (localStream) {
            localStream.getTracks().forEach(function(track) { track.stop(); });
            localStream = null;
        }
        mediaReady = false;
        if (notify) {
            socket.emit('call_ended', { room: roomId });
            socket.emit('leave_call', { room: roomId, user_id: myUserId });
        }
        setTimeout(function() {
            window.location.href = redirectUrl;
        }, 1000);
    }

    endCallBtn.addEventListener('click', function() {
        endCall(true);
    });

    window.addEventListener('beforeunload', function() {
        if (localStream) {
            localStream.getTracks().forEach(function(track) { track.stop(); });
        }
        socket.emit('leave_call', { room: roomId, user_id: myUserId });
    });

    startCall();
})();

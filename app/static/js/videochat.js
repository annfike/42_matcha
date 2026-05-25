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
    var localPlaceholder = document.getElementById('local-placeholder');
    var remoteVideo = document.getElementById('remote-video');
    var remotePlaceholder = document.getElementById('remote-placeholder');
    var statusEl = document.getElementById('call-status');
    var toggleVideoBtn = document.getElementById('toggle-video');
    var toggleAudioBtn = document.getElementById('toggle-audio');
    var endCallBtn = document.getElementById('end-call');

    var localStream = null;
    var remoteStream = null;
    var peerConnection = null;
    var videoEnabled = true;
    var audioEnabled = true;
    var mediaReady = false;
    var makingOffer = false;
    var pendingOffer = null;
    var pendingAnswer = null;
    var pendingIceCandidates = [];

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

    function playVideo(el) {
        if (!el || !el.srcObject) return;
        var p = el.play();
        if (p && typeof p.catch === 'function') {
            p.catch(function(err) {
                console.warn('video.play():', err);
            });
        }
    }

    function mediaErrorMessage(err) {
        if (!err) return 'Could not access camera or microphone.';
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            return 'Camera/microphone blocked. Allow access in the browser address bar and try again.';
        }
        if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
            return 'No camera or microphone found. Plug in a webcam/mic, check System Settings → Privacy (Camera/Microphone) for your browser, then reload. You can still test with audio-only if a mic is available.';
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

    async function detectInputs() {
        var hasVideo = false;
        var hasAudio = false;
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
            return { hasVideo: true, hasAudio: true };
        }
        var devices = await navigator.mediaDevices.enumerateDevices();
        hasVideo = devices.some(function(d) { return d.kind === 'videoinput'; });
        hasAudio = devices.some(function(d) { return d.kind === 'audioinput'; });
        if (!hasVideo && !hasAudio) {
            try {
                var tmp = await navigator.mediaDevices.getUserMedia({ audio: true });
                tmp.getTracks().forEach(function(t) { t.stop(); });
                devices = await navigator.mediaDevices.enumerateDevices();
                hasVideo = devices.some(function(d) { return d.kind === 'videoinput'; });
                hasAudio = devices.some(function(d) { return d.kind === 'audioinput'; });
            } catch (probeErr) {
                console.warn('Device probe failed:', probeErr);
            }
        }
        return { hasVideo: hasVideo, hasAudio: hasAudio };
    }

    function showLocalNoCamera() {
        if (localVideo) localVideo.style.display = 'none';
        if (localPlaceholder) localPlaceholder.style.display = 'flex';
        if (toggleVideoBtn) toggleVideoBtn.disabled = true;
    }

    function showLocalPreview() {
        if (localVideo) localVideo.style.display = 'block';
        if (localPlaceholder) localPlaceholder.style.display = 'none';
        if (toggleVideoBtn) toggleVideoBtn.disabled = false;
    }

    async function acquireLocalMedia() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('getUserMedia is not supported in this browser');
        }
        var inputs = await detectInputs();
        var attempts = [];
        if (inputs.hasVideo && inputs.hasAudio) {
            attempts.push({ video: true, audio: true });
        }
        if (inputs.hasVideo) {
            attempts.push({ video: true, audio: false });
        }
        if (inputs.hasAudio) {
            attempts.push({ video: false, audio: true });
        }
        if (attempts.length === 0) {
            var noDev = new Error('No videoinput or audioinput devices reported by the browser.');
            noDev.name = 'NotFoundError';
            throw noDev;
        }
        var lastErr = null;
        for (var i = 0; i < attempts.length; i++) {
            try {
                return await navigator.mediaDevices.getUserMedia(attempts[i]);
            } catch (err) {
                lastErr = err;
                if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    throw err;
                }
                if (err.name !== 'NotFoundError' && err.name !== 'DevicesNotFoundError' &&
                    err.name !== 'OverconstrainedError') {
                    console.warn('getUserMedia failed:', attempts[i], err);
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

    function markConnected() {
        updateStatus('Connected', 'connected');
    }

    function attachRemoteStream(stream) {
        if (!stream) return;
        remoteStream = stream;
        remoteVideo.srcObject = stream;
        remotePlaceholder.style.display = 'none';
        playVideo(remoteVideo);
        markConnected();
    }

    function onRemoteTrack(event) {
        if (event.streams && event.streams[0]) {
            attachRemoteStream(event.streams[0]);
            return;
        }
        if (!event.track) return;
        if (!remoteStream) {
            remoteStream = new MediaStream();
            remoteVideo.srcObject = remoteStream;
        }
        var exists = remoteStream.getTracks().some(function(t) { return t.id === event.track.id; });
        if (!exists) {
            remoteStream.addTrack(event.track);
        }
        remotePlaceholder.style.display = 'none';
        playVideo(remoteVideo);
        markConnected();
    }

    async function drainIceCandidates() {
        if (!peerConnection || !peerConnection.remoteDescription) return;
        var queue = pendingIceCandidates.slice();
        pendingIceCandidates = [];
        for (var i = 0; i < queue.length; i++) {
            try {
                await peerConnection.addIceCandidate(new RTCIceCandidate(queue[i]));
            } catch (e) {
                console.error('ICE error:', e);
            }
        }
    }

    async function addIceCandidateSafe(candidate) {
        if (!candidate || !peerConnection) {
            if (candidate) pendingIceCandidates.push(candidate);
            return;
        }
        if (!peerConnection.remoteDescription) {
            pendingIceCandidates.push(candidate);
            return;
        }
        try {
            await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
        } catch (e) {
            console.error('ICE error:', e);
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
        peerConnection.ontrack = onRemoteTrack;
        peerConnection.onicecandidate = function(event) {
            if (event.candidate) {
                socket.emit('ice_candidate', { room: roomId, candidate: event.candidate });
            }
        };
        peerConnection.onconnectionstatechange = function() {
            if (!peerConnection) return;
            var state = peerConnection.connectionState;
            if (state === 'connected') {
                markConnected();
            } else if (state === 'connecting') {
                updateStatus('Connecting...', '');
            } else if (state === 'disconnected' || state === 'failed') {
                updateStatus('Connection lost', 'error');
            }
        };
        peerConnection.oniceconnectionstatechange = function() {
            if (!peerConnection) return;
            var ice = peerConnection.iceConnectionState;
            if (ice === 'connected' || ice === 'completed') {
                markConnected();
            } else if (ice === 'failed' || ice === 'disconnected') {
                updateStatus('Connection lost', 'error');
            }
        };
        return peerConnection;
    }

    async function handleOffer(data) {
        if (!data || !data.offer) return;
        try {
            if (!isIncoming && makingOffer) return;
            createPeerConnection();
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
            await drainIceCandidates();
            var answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            socket.emit('answer', { room: roomId, answer: answer });
            updateStatus('Connecting...', '');
        } catch (err) {
            console.error('Answer error:', err);
            updateStatus('Could not connect to caller', 'error');
        }
    }

    async function handleAnswer(data) {
        if (!data || !data.answer) return;
        if (!peerConnection) {
            pendingAnswer = data;
            return;
        }
        try {
            await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
            await drainIceCandidates();
            updateStatus('Connecting...', '');
        } catch (err) {
            console.error('Remote description error:', err);
        }
    }

    async function flushPendingSignaling() {
        if (pendingOffer && mediaReady) {
            var offer = pendingOffer;
            pendingOffer = null;
            await handleOffer(offer);
        }
        if (pendingAnswer && peerConnection) {
            var answer = pendingAnswer;
            pendingAnswer = null;
            await handleAnswer(answer);
        }
    }

    async function startCall() {
        try {
            updateStatus('Requesting camera and microphone...');
            localStream = await acquireLocalMedia();
            mediaReady = true;
            videoEnabled = localStream.getVideoTracks().length > 0;
            audioEnabled = localStream.getAudioTracks().length > 0;
            if (videoEnabled) {
                showLocalPreview();
                localVideo.srcObject = localStream;
                playVideo(localVideo);
            } else {
                showLocalNoCamera();
            }
            if (!videoEnabled && audioEnabled) {
                updateStatus('No camera — audio only. Remote video can still work.', '');
            } else if (!audioEnabled) {
                updateStatus('No microphone detected.', 'error');
            }

            socket.emit('join_call', { room: roomId, user_id: myUserId });

            await flushPendingSignaling();

            if (isIncoming) {
                updateStatus('Connecting...', '');
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
            updateStatus('Connecting...', '');
            makingOffer = true;
            createPeerConnection();
            var offer = await peerConnection.createOffer({
                offerToReceiveAudio: true,
                offerToReceiveVideo: true
            });
            await peerConnection.setLocalDescription(offer);
            socket.emit('offer', { room: roomId, offer: offer });
            makingOffer = false;
            await flushPendingSignaling();
        } catch (err) {
            makingOffer = false;
            console.error('Offer error:', err);
            updateStatus('Could not start connection', 'error');
        }
    });

    socket.on('offer', async function(data) {
        if (!data || !data.offer) return;
        if (!mediaReady) {
            pendingOffer = data;
            return;
        }
        await handleOffer(data);
    });

    socket.on('answer', async function(data) {
        await handleAnswer(data);
    });

    socket.on('ice_candidate', async function(data) {
        if (data && data.candidate) {
            await addIceCandidateSafe(data.candidate);
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
        remoteStream = null;
        mediaReady = false;
        pendingOffer = null;
        pendingAnswer = null;
        pendingIceCandidates = [];
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

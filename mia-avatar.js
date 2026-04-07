// ======================
// Inicializacion de PIXI
// ======================

window.__MIA_AVATAR_LOADED__ = true
window.__MIA_AVATAR_READY__ = false
window.__MIA_AVATAR_ERROR__ = ""
window.__MIA_AVATAR_TICKS__ = 0

const app = new PIXI.Application({
	width: 800,
	height: 800,
	backgroundColor: 0x81d2bc
})

function getAppCanvas() {
	return app.canvas || app.view
}

function mountCanvasIfNeeded() {
	const canvas = getAppCanvas()
	if (canvas && !canvas.isConnected) {
		document.body.appendChild(canvas)
	}
}

function onRenderTick() {
	window.__MIA_AVATAR_TICKS__ += 1
	const now = performance.now()
	const dt = app.ticker.deltaMS / 1000
	headFloatTimer += dt
	breathTimer += dt
	idleEyeDriftTimer += dt
	idleMouthPulseTimer += dt

	const headFloatY = Math.sin(headFloatTimer * 1.8) * 1.6
	const breathingScale = 1 + ((Math.sin((breathTimer * Math.PI * 2) / 3.6) + 1) * 0.5) * 0.01
	avatarContainer.position.set(BASE_AVATAR_X, BASE_AVATAR_Y + headFloatY)
	avatarContainer.scale.set(breathingScale)

	if (!speaking && now >= nextIdleLookAt && now - lastMouseMoveAt > 800) {
		idleLookOffsetX = randomRange(-5, 5)
		idleLookOffsetY = randomRange(-3.5, 3.5)
		idleLookActiveUntil = now + randomRange(700, 1400)
		nextIdleLookAt = now + randomRange(3000, 6000)
	}

	const mouseIsActive = now - lastMouseMoveAt < 700
	if (mouseIsActive) {
		targetEyeOffsetX = mouseEyeOffsetX
		targetEyeOffsetY = mouseEyeOffsetY
	} else if (!speaking) {
		const driftX = Math.sin(idleEyeDriftTimer * 1.35) * 2.1
		const driftY = Math.cos(idleEyeDriftTimer * 1.1) * 1.3

		if (now < idleLookActiveUntil) {
			targetEyeOffsetX = idleLookOffsetX + driftX
			targetEyeOffsetY = idleLookOffsetY + driftY
		} else {
			targetEyeOffsetX = driftX
			targetEyeOffsetY = driftY
		}
	} else {
		targetEyeOffsetX = 0
		targetEyeOffsetY = 0
	}

	const eyeLerp = mouseIsActive ? 0.22 : 0.1
	currentEyeOffsetX = lerp(currentEyeOffsetX, targetEyeOffsetX, eyeLerp)
	currentEyeOffsetY = lerp(currentEyeOffsetY, targetEyeOffsetY, eyeLerp)

	const emotionEye = getEmotionEyeStyle()
	targetEyeScale = emotionEye.scale
	currentEyeScale = lerp(currentEyeScale, targetEyeScale, 0.12)

	leftEye.x = BASE_LEFT_EYE_X + currentEyeOffsetX + emotionEye.innerOffset
	rightEye.x = BASE_RIGHT_EYE_X + currentEyeOffsetX - emotionEye.innerOffset
	leftEye.y = BASE_LEFT_EYE_Y + currentEyeOffsetY + emotionEye.yOffset
	rightEye.y = BASE_RIGHT_EYE_Y + currentEyeOffsetY + emotionEye.yOffset
	leftEye.scale.x = currentEyeScale
	rightEye.scale.x = currentEyeScale
	leftEye.scale.y = currentEyeScale * blinkEyeScaleY
	rightEye.scale.y = currentEyeScale * blinkEyeScaleY

	currentAmplitude = getEffectiveAmplitude()

	const ampLerp = speaking ? 0.35 : 0.12
	smoothedAmplitude = lerp(smoothedAmplitude, currentAmplitude, ampLerp)

	if (speaking && now - lastChunkAt < 120 && smoothedAmplitude < 0.008) {
		smoothedAmplitude = 0.012
	}

	let nextMouthType = amplitudeToMouthType(smoothedAmplitude)

	if (!speaking) {
		const idleType = getIdleExpressionType(now)
		nextMouthType = idleType || getEmotionIdleMouthType()
	}

	currentMouthType = nextMouthType
	applyMouthTargetsForState(currentMouthType, smoothedAmplitude)

	if (!speaking) {
		const pulse = (Math.sin(idleMouthPulseTimer * 2.8) + 1) * 0.5
		targetMouthHeight += pulse * 2.2
		targetMouthWidth += Math.sin(idleMouthPulseTimer * 1.9) * 1.2
	}

	const mouthLerp = 0.15
	currentMouthWidth = lerp(currentMouthWidth, targetMouthWidth, mouthLerp)
	currentMouthHeight = lerp(currentMouthHeight, targetMouthHeight, mouthLerp)

	if (speaking) {
		mouthContainer.y = BASE_MOUTH_Y
	} else {
		idlePhase += dt
		mouthContainer.y = BASE_MOUTH_Y + Math.sin(idlePhase * avatarPreset.idleBobSpeed) * avatarPreset.idleBobAmount
	}

	maybeRedrawMouth(currentMouthType, currentMouthWidth, currentMouthHeight)
}

Promise.resolve(typeof app.init === "function" ? app.init({ width: 800, height: 800, background: 0x81d2bc }) : null)
	.then(() => {
		mountCanvasIfNeeded()
		if (!app.stage || typeof app.stage.addChild !== "function") {
			throw new Error("PIXI stage no disponible tras init")
		}
		if (!avatarContainer.parent) {
			app.stage.addChild(avatarContainer)
		}
		if (!app.ticker || typeof app.ticker.add !== "function") {
			throw new Error("PIXI ticker no disponible tras init")
		}
		app.ticker.add(onRenderTick)
		if (app.ticker && typeof app.ticker.start === "function") {
			app.ticker.start()
		}
		if (typeof app.start === "function") {
			app.start()
		}
		window.__MIA_AVATAR_READY__ = true
	})
	.catch((error) => {
		window.__MIA_AVATAR_ERROR__ = String(error && error.message ? error.message : error)
	})

const avatarContainer = new PIXI.Container()
const BASE_AVATAR_X = 400
const BASE_AVATAR_Y = 400
avatarContainer.pivot.set(BASE_AVATAR_X, BASE_AVATAR_Y)
avatarContainer.position.set(BASE_AVATAR_X, BASE_AVATAR_Y)

// =====================
// Cabeza
// =====================

const head = new PIXI.Graphics()
head.beginFill(0xa9eccc)
head.drawRoundedRect(50, 50, 700, 700, 30)
head.endFill()
avatarContainer.addChild(head)

// =====================
// Ojos
// =====================

const leftEye = new PIXI.Graphics()
leftEye.beginFill(0x000000)
leftEye.drawCircle(0, 0, 10)
leftEye.endFill()
const BASE_LEFT_EYE_X = 306
const BASE_LEFT_EYE_Y = 353
const BASE_RIGHT_EYE_X = 493
const BASE_RIGHT_EYE_Y = 353
leftEye.x = BASE_LEFT_EYE_X
leftEye.y = BASE_LEFT_EYE_Y

const rightEye = new PIXI.Graphics()
rightEye.beginFill(0x000000)
rightEye.drawCircle(0, 0, 10)
rightEye.endFill()
rightEye.x = BASE_RIGHT_EYE_X
rightEye.y = BASE_RIGHT_EYE_Y

avatarContainer.addChild(leftEye)
avatarContainer.addChild(rightEye)

// =====================
// Boca + expresiones
// =====================

const mouthContainer = new PIXI.Container()
const mouthFrame = new PIXI.Graphics()
const mouthInside = new PIXI.Graphics()
const teeth = new PIXI.Graphics()
const tongue = new PIXI.Graphics()

mouthContainer.addChild(mouthFrame)
mouthContainer.addChild(mouthInside)
mouthContainer.addChild(teeth)
mouthContainer.addChild(tongue)

// Keep teeth and tongue clipped by the interior shape.
teeth.mask = mouthInside
tongue.mask = mouthInside

const BASE_MOUTH_X = 400
const BASE_MOUTH_Y = 493

let emotion = "happy" // neutral | happy | curious | thinking | surprised

const AVATAR_PRESETS = {
	alegre: {
		emotion: "happy",
		idleMinMs: 3200,
		idleMaxMs: 5000,
		idleHoldMinMs: 450,
		idleHoldMaxMs: 1000,
		blinkMinMs: 2400,
		blinkMaxMs: 4200,
		doubleBlinkChance: 0.3,
		ampSmall: 0.016,
		ampMedium: 0.03,
		idleBobAmount: 1.9,
		idleBobSpeed: 2.4
	},
	serio: {
		emotion: "thinking",
		idleMinMs: 5000,
		idleMaxMs: 7000,
		idleHoldMinMs: 280,
		idleHoldMaxMs: 650,
		blinkMinMs: 2900,
		blinkMaxMs: 5200,
		doubleBlinkChance: 0.12,
		ampSmall: 0.02,
		ampMedium: 0.038,
		idleBobAmount: 1.1,
		idleBobSpeed: 1.8
	},
	curioso: {
		emotion: "curious",
		idleMinMs: 3600,
		idleMaxMs: 5600,
		idleHoldMinMs: 350,
		idleHoldMaxMs: 850,
		blinkMinMs: 2300,
		blinkMaxMs: 4300,
		doubleBlinkChance: 0.26,
		ampSmall: 0.017,
		ampMedium: 0.032,
		idleBobAmount: 1.7,
		idleBobSpeed: 2.2
	}
}

let avatarPreset = { ...AVATAR_PRESETS.alegre }

let currentMouthType = "neutral"
let targetMouthWidth = 50
let targetMouthHeight = 4
let currentMouthWidth = 50
let currentMouthHeight = 4
let speaking = false  // Inicialmente NO está hablando

let lastDrawnMouthType = ""
let lastDrawnWidth = -1
let lastDrawnHeight = -1
let lastDrawnAmp = -1
let currentTongueYOffset = 0
let currentTongueScaleY = 1

let idlePhase = 0
let idleExpressionType = ""
let idleExpressionUntil = 0
let emotionalMouthUntil = 0  // Force emotion mouth shape for first N ms after emotion change

// =====================
// Estado de animacion viva (ojos/cabeza/respiracion/idle)
// =====================

let targetEyeOffsetX = 0
let targetEyeOffsetY = 0
let currentEyeOffsetX = 0
let currentEyeOffsetY = 0
let mouseEyeOffsetX = 0
let mouseEyeOffsetY = 0
let lastMouseMoveAt = 0
let idleLookOffsetX = 0
let idleLookOffsetY = 0
let idleLookActiveUntil = 0
let nextIdleLookAt = performance.now() + randomRange(3000, 6000)

let targetEyeScale = 1
let currentEyeScale = 1
let blinkEyeScaleY = 1

let headFloatTimer = 0
let breathTimer = 0
let idleEyeDriftTimer = 0
let idleMouthPulseTimer = 0

function randomRange(min, max) {
	return min + Math.random() * (max - min)
}

let nextIdleExpressionAt = performance.now() + randomRange(avatarPreset.idleMinMs, avatarPreset.idleMaxMs)

function lerp(from, to, alpha) {
	return from + (to - from) * alpha
}

function clamp(value, min, max) {
	return Math.max(min, Math.min(max, value))
}

function getEmotionEyeStyle() {
	if (emotion === "happy") {
		return { innerOffset: 2.2, yOffset: 0, scale: 1.0 }
	}

	if (emotion === "curious") {
		return { innerOffset: -2.4, yOffset: 0, scale: 1.0 }
	}

	if (emotion === "thinking") {
		return { innerOffset: 0, yOffset: 1.6, scale: 1.0 }
	}

	if (emotion === "surprised") {
		return { innerOffset: 0, yOffset: -0.5, scale: 1.12 }
	}

	return { innerOffset: 0, yOffset: 0, scale: 1.0 }
}

window.addEventListener("mousemove", (event) => {
	const canvas = getAppCanvas()
	if (!canvas) {
		return
	}

	const rect = canvas.getBoundingClientRect()
	if (!rect.width || !rect.height) {
		return
	}

	const localX = event.clientX - rect.left
	const localY = event.clientY - rect.top
	const normX = (localX - BASE_AVATAR_X) / (rect.width * 0.5)
	const normY = (localY - BASE_AVATAR_Y) / (rect.height * 0.5)

	mouseEyeOffsetX = clamp(normX * 6, -6, 6)
	mouseEyeOffsetY = clamp(normY * 4.5, -4.5, 4.5)
	lastMouseMoveAt = performance.now()
})


function drawMouth(type = "neutral", width = 50, height = 4, amplitude = 0) {
	const w = Math.max(10, width)
	const h = Math.max(4, height)
	const amp = clamp((amplitude - 0.006) / 0.05, 0, 1)

	const outlineColor = 0x000000
	const mouthFill = 0x3EDC81
	const tongueColor = 0x1FAF6A
	const teethColor = 0xFFFFFF

	let mouthW = w
	let mouthH = h
	if (speaking) {
		mouthW *= 1 + amp * 0.14
		mouthH *= 1 + amp * 0.22
	}

	// Smile: draw as a bezier arc curve instead of a rectangle
	if (type === "smile") {
		mouthFrame.clear()
		mouthInside.clear()
		teeth.clear()
		tongue.clear()
		currentTongueYOffset = lerp(currentTongueYOffset, 0, 0.15)
		currentTongueScaleY = lerp(currentTongueScaleY, 1, 0.15)
		const lw = Math.max(4, Math.round(w * 0.1))
		const sw = w * 0.46
		const sh = Math.max(6, h * 1.35)

		// Base visible mouth so the smile never disappears visually.
		mouthFrame.beginFill(outlineColor)
		mouthFrame.drawRoundedRect(-sw, -lw * 0.3, sw * 2, lw * 0.75, lw * 0.35)
		mouthFrame.endFill()

		mouthInside.beginFill(mouthFill)
		mouthInside.drawRoundedRect(-(sw - lw * 0.6), -lw * 0.15, (sw - lw * 0.6) * 2, lw * 0.38, lw * 0.2)
		mouthInside.endFill()

		mouthFrame.lineStyle(lw, outlineColor, 1)
		mouthFrame.moveTo(-sw, 0)
		mouthFrame.bezierCurveTo(-sw * 0.88, sh * 1.8, sw * 0.88, sh * 1.8, sw, 0)
		return
	}

	if (type === "sad") {
		mouthW *= 0.9
		mouthH *= 0.62
	}

	if (type === "neutral") {
		mouthH *= 0.65
	}

	const stroke = Math.max(2, Math.min(4, Math.round(Math.min(mouthW, mouthH) * 0.12)))
	const frameRadius = Math.max(2, Math.min(mouthW, mouthH) * 0.42)

	// Depth 1: mouthFrame
	mouthFrame.clear()
	mouthFrame.lineStyle(0)
	mouthFrame.beginFill(outlineColor)
	mouthFrame.drawRoundedRect(-mouthW / 2, -mouthH / 2, mouthW, mouthH, frameRadius)
	mouthFrame.endFill()

	const inset = Math.max(1.5, stroke * 0.82)
	const innerW = Math.max(2, mouthW - inset * 2)
	const innerH = Math.max(2, mouthH - inset * 2)
	const innerRadius = Math.max(2, frameRadius - inset * 0.6)
	const mouthTop = -innerH / 2
	const mouthCenter = 0

	// Depth 2: mouthInside (also mask)
	mouthInside.clear()
	mouthInside.lineStyle(0)
	mouthInside.beginFill(mouthFill)
	mouthInside.drawRoundedRect(-innerW / 2, -innerH / 2, innerW, innerH, innerRadius)
	mouthInside.endFill()

	const openState = type === "talkSmall" || type === "talkMedium" || type === "talkBig" || type === "surprised"

	// Depth 3: teeth
	teeth.clear()
	if (openState) {
		const teethW = innerW * 0.78
		const teethH = Math.max(2, innerH * 0.2)
		const teethY = mouthTop + innerH * 0.15
		teeth.lineStyle(0)
		teeth.beginFill(teethColor)
		teeth.drawRoundedRect(-teethW / 2, teethY, teethW, teethH, Math.max(1.5, teethH * 0.32))
		teeth.endFill()
	}

	// Depth 4: tongue
	tongue.clear()
	if (openState) {
		const tongueRx = Math.max(2, innerW * 0.27)
		const tongueBaseRy = Math.max(2, innerH * 0.2)
		const targetOffset = amp * 8
		const targetScale = 1 + amp * 0.4
		currentTongueYOffset = lerp(currentTongueYOffset, targetOffset, 0.15)
		currentTongueScaleY = lerp(currentTongueScaleY, targetScale, 0.15)
		const tongueRy = tongueBaseRy * currentTongueScaleY
		const tongueCy = mouthCenter + innerH * 0.25 + currentTongueYOffset

		tongue.lineStyle(1, outlineColor, 0.35)
		tongue.beginFill(tongueColor)
		tongue.drawEllipse(0, tongueCy, tongueRx, tongueRy)
		tongue.endFill()
	} else {
		currentTongueYOffset = lerp(currentTongueYOffset, 0, 0.15)
		currentTongueScaleY = lerp(currentTongueScaleY, 1, 0.15)
	}
}

function getMouthBaseByType(type) {

	if (type === "neutral") return { width: 50, height: 6 }

	if (type === "smile") return { width: 38, height: 9 }

	if (type === "talkSmall") return { width: 32, height: 14 }

	if (type === "talkMedium") return { width: 38, height: 22 }

	if (type === "talkBig") return { width: 44, height: 30 }

	if (type === "surprised") return { width: 24, height: 30 }

	if (type === "sad") return { width: 42, height: 14 }

	return { width: 50, height: 6 }
}

function getEmotionIdleMouthType() {
	if (emotion === "happy") return "smile"
	if (emotion === "surprised") return "surprised"
	if (emotion === "curious") return "talkSmall"
	if (emotion === "thinking") return "neutral"
	return "smile"  // Neutral expression is a light smile
}

function getIdleExpressionType(now) {
	if (now < idleExpressionUntil && idleExpressionType) {
		return idleExpressionType
	}

	if (now >= nextIdleExpressionAt) {
		const roll = Math.random()

		if (roll < 0.68) {
			idleExpressionType = "smile"
		} else if (roll < 0.82) {
			idleExpressionType = "smile"  // Light smile variation
		} else if (roll < 0.93) {
			idleExpressionType = "surprised"
		} else {
			idleExpressionType = "sad"
		}

		idleExpressionUntil = now + randomRange(avatarPreset.idleHoldMinMs, avatarPreset.idleHoldMaxMs)
		nextIdleExpressionAt = now + randomRange(avatarPreset.idleMinMs, avatarPreset.idleMaxMs)
		return idleExpressionType
	}

	return ""
}

function applyMouthTargetsForState(type, amp) {
	const base = getMouthBaseByType(type)
	let width = base.width
	let height = base.height

	if (speaking && (type === "talkSmall" || type === "talkMedium" || type === "talkBig" || type === "surprised")) {
		const ampBoost = clamp((amp - 0.008) / 0.05, 0, 1)
		height *= 0.9 + ampBoost * 0.3
		width *= 0.95 + ampBoost * 0.12
	}

	if (!speaking && emotion === "thinking" && type === "neutral") {
		width = 36
		height = 3
	}

	targetMouthWidth = width
	targetMouthHeight = height
}

function maybeRedrawMouth(type, width, height) {
	const widthChanged = Math.abs(width - lastDrawnWidth) > 0.35
	const heightChanged = Math.abs(height - lastDrawnHeight) > 0.35
	const typeChanged = type !== lastDrawnMouthType
	const ampChanged = Math.abs(smoothedAmplitude - lastDrawnAmp) > 0.004

	if (!typeChanged && !widthChanged && !heightChanged && !ampChanged) {
		return
	}

	drawMouth(type, width, height, smoothedAmplitude)
	lastDrawnMouthType = type
	lastDrawnWidth = width
	lastDrawnHeight = height
	lastDrawnAmp = smoothedAmplitude
}

// Opcional: permite cambiar emocion desde fuera sin tocar la canalizacion de audio/WS.
window.setAvatarEmotion = (nextEmotion) => {
	const valid = ["neutral", "happy", "curious", "thinking", "surprised"]
	if (valid.includes(nextEmotion)) {
		emotion = nextEmotion
		// Force emotion mouth shape for 2.5 seconds after emotion change
		emotionalMouthUntil = performance.now() + 2500
	}
}

window.setAvatarPreset = (presetName) => {
	if (!AVATAR_PRESETS[presetName]) {
		return
	}

	avatarPreset = { ...AVATAR_PRESETS[presetName] }
	emotion = avatarPreset.emotion
	nextIdleExpressionAt = performance.now() + randomRange(avatarPreset.idleMinMs, avatarPreset.idleMaxMs)
}

mouthContainer.x = BASE_MOUTH_X
mouthContainer.y = BASE_MOUTH_Y
drawMouth("neutral", 50, 8, 0)
avatarContainer.addChild(mouthContainer)

// =====================
// Estado Lip Sync
// =====================

let currentAmplitude = 0
let smoothedAmplitude = 0
let chunkAmplitude = 0
let lastChunkAt = 0
let audioReady = false
let pendingChunks = [] // Buffer para chunks que llegan antes de que el audio este listo
let speakingTimeoutId = null  // Timeout para forzar idle
const SPEAKING_WATCHDOG_MS = 22000

function clearSpeakingWatchdog() {
	if (speakingTimeoutId) {
		clearTimeout(speakingTimeoutId)
		speakingTimeoutId = null
	}
}

function bumpSpeakingWatchdog() {
	clearSpeakingWatchdog()
	speakingTimeoutId = setTimeout(() => {
		speaking = false
		idleExpressionType = ""
		idleExpressionUntil = 0
		speakingTimeoutId = null
	}, SPEAKING_WATCHDOG_MS)
}

// =====================
// WebAudio (analisis)
// =====================

let audioContext = null
let analyser = null
let lipGain = null
let outputGain = null
let timeDomainData = null
let frequencyData = null
let nextChunkTime = 0

let lowStartBin = 0
let lowEndBin = 0
let midStartBin = 0
let midEndBin = 0
let highStartBin = 0
let highEndBin = 0

let visemeCandidate = "neutral"
let lastVisemeCandidate = "neutral"
let stableViseme = "neutral"
let visemeStableFrames = 0
const VISEME_STABLE_FRAMES_REQUIRED = 3
const SPEECH_SILENCE_THRESHOLD = 0.008

function clampBin(value, maxBin) {
	return clamp(value, 0, maxBin)
}

function configureFrequencyBands() {
	if (!audioContext || !analyser) {
		return
	}

	const nyquist = audioContext.sampleRate * 0.5
	const maxBin = analyser.frequencyBinCount - 1

	const hzToBin = (hz) => clampBin(Math.floor((hz / nyquist) * analyser.frequencyBinCount), maxBin)

	lowStartBin = hzToBin(80)
	lowEndBin = Math.max(lowStartBin + 1, hzToBin(300))
	midStartBin = hzToBin(300)
	midEndBin = Math.max(midStartBin + 1, hzToBin(1500))
	highStartBin = hzToBin(1500)
	highEndBin = Math.max(highStartBin + 1, hzToBin(4000))
}

function averageBandEnergy(startBin, endBin) {
	if (!frequencyData) {
		return 0
	}

	const start = Math.max(0, startBin)
	const end = Math.min(frequencyData.length, endBin)
	if (end <= start) {
		return 0
	}

	let sum = 0
	for (let i = start; i < end; i++) {
		sum += frequencyData[i]
	}

	return (sum / (end - start)) / 255
}

function estimateVisemeFromBands(lowEnergy, midEnergy, highEnergy) {
	if (lowEnergy > 0.28 && midEnergy > 0.2) {
		return "A"
	}

	if (highEnergy > 0.19 && highEnergy > midEnergy * 1.08) {
		return "I"
	}

	if (midEnergy > lowEnergy * 1.15 && midEnergy >= highEnergy) {
		return "E"
	}

	if (lowEnergy > 0.24 && midEnergy < lowEnergy * 0.72) {
		return "O"
	}

	if (lowEnergy > 0.2 && midEnergy > 0.11 && midEnergy < lowEnergy) {
		return "U"
	}

	return "neutral"
}

function updateStableViseme(candidate, amplitude) {
	if (!speaking || amplitude < SPEECH_SILENCE_THRESHOLD) {
		visemeCandidate = "neutral"
		lastVisemeCandidate = "neutral"
		stableViseme = "neutral"
		visemeStableFrames = 0
		return stableViseme
	}

	visemeCandidate = candidate
	if (visemeCandidate === lastVisemeCandidate) {
		visemeStableFrames += 1
	} else {
		lastVisemeCandidate = visemeCandidate
		visemeStableFrames = 1
	}

	if (visemeStableFrames >= VISEME_STABLE_FRAMES_REQUIRED) {
		stableViseme = visemeCandidate
	}

	return stableViseme
}

function visemeToMouthType(viseme) {
	if (viseme === "A") return "talkBig"
	if (viseme === "E") return "talkMedium"
	if (viseme === "I") return "talkSmall"
	if (viseme === "O") return "surprised"
	if (viseme === "U") return "talkSmall"
	return "neutral"
}

function initAudioContext() {
	if (audioContext) {
		return
	}

	audioContext = new (window.AudioContext || window.webkitAudioContext)()
	analyser = audioContext.createAnalyser()
	analyser.fftSize = 1024

	lipGain = audioContext.createGain()
	lipGain.gain.value = 1
	outputGain = audioContext.createGain()
	outputGain.gain.value = 0
	lipGain.connect(analyser)
	analyser.connect(outputGain)
	outputGain.connect(audioContext.destination)

	timeDomainData = new Uint8Array(analyser.fftSize)
	frequencyData = new Uint8Array(analyser.frequencyBinCount)
	configureFrequencyBands()
	nextChunkTime = 0
}

async function unlockAudioFromGesture() {
	if (!audioContext) {
		initAudioContext()
	}

	const running = await ensureAudioRunning()
	if (!running) {
		return false
	}

	audioReady = true
	processPendingChunks()
	return true
}

async function ensureAudioRunning() {
	if (!audioContext) {
		return false
	}

	if (audioContext.state !== "running") {
		try {
			await audioContext.resume()
		} catch (error) {
			return false
		}
	}

	return true
}

// =====================
// Utilidades de audio
// =====================

function base64ToArrayBuffer(base64) {
	const binary = atob(base64)
	const length = binary.length
	const bytes = new Uint8Array(length)

	for (let i = 0; i < length; i++) {
		bytes[i] = binary.charCodeAt(i)
	}

	return bytes.buffer
}

function playPcmFloatChunk(base64Data, sampleRate = 22050, channels = 1) {
	const rawBuffer = base64ToArrayBuffer(base64Data)
	const floatData = new Float32Array(rawBuffer)

	if (!floatData.length) {
		return
	}

	// Calcular amplitud incluso si no está listo para reproducir
	let sum = 0
	for (let i = 0; i < floatData.length; i++) {
		const value = floatData[i]
		sum += value * value
	}
	chunkAmplitude = Math.sqrt(sum / floatData.length)
	lastChunkAt = performance.now()

	// Si el audio no esta listo, guardar en buffer.
	if (!audioContext || !audioReady) {
		pendingChunks.push({ base64Data, sampleRate, channels })
		return
	}

	const frameCount = Math.floor(floatData.length / channels)
	if (frameCount <= 0) {
		return
	}

	const audioBuffer = audioContext.createBuffer(channels, frameCount, sampleRate)

	for (let ch = 0; ch < channels; ch++) {
		const channelData = audioBuffer.getChannelData(ch)
		let readIndex = ch

		for (let i = 0; i < frameCount; i++) {
			channelData[i] = floatData[readIndex]
			readIndex += channels
		}
	}

	const source = audioContext.createBufferSource()
	source.buffer = audioBuffer
	source.connect(lipGain)

	const now = audioContext.currentTime
	if (nextChunkTime < now) {
		nextChunkTime = now
	}

	source.start(nextChunkTime)
	nextChunkTime += audioBuffer.duration
}

function processPendingChunks() {
	if (!audioReady || pendingChunks.length === 0) {
		return
	}

	while (pendingChunks.length > 0) {
		const chunk = pendingChunks.shift()
		playPcmFloatChunk(chunk.base64Data, chunk.sampleRate, chunk.channels)
	}
}

function getEffectiveAmplitude() {
	let analyserRms = 0

	if (analyser && timeDomainData && frequencyData) {
		analyser.getByteTimeDomainData(timeDomainData)
		analyser.getByteFrequencyData(frequencyData)

		let sum = 0
		for (let i = 0; i < timeDomainData.length; i++) {
			const centered = (timeDomainData[i] - 128) / 128
			sum += centered * centered
		}
		analyserRms = Math.sqrt(sum / timeDomainData.length)

		const lowEnergy = averageBandEnergy(lowStartBin, lowEndBin)
		const midEnergy = averageBandEnergy(midStartBin, midEndBin)
		const highEnergy = averageBandEnergy(highStartBin, highEndBin)
		const rawViseme = estimateVisemeFromBands(lowEnergy, midEnergy, highEnergy)
		updateStableViseme(rawViseme, Math.max(analyserRms, chunkAmplitude))
	} else {
		updateStableViseme("neutral", 0)
	}

	const combined = Math.max(analyserRms, chunkAmplitude)
	chunkAmplitude *= 0.9
	return combined
}

function amplitudeToMouthType(amplitude) {
	if (!speaking || amplitude < SPEECH_SILENCE_THRESHOLD) {
		return "neutral"
	}

	const mappedType = visemeToMouthType(stableViseme)
	if (mappedType === "neutral") {
		if (amplitude < avatarPreset.ampSmall) return "talkSmall"
		if (amplitude < avatarPreset.ampMedium) return "talkMedium"
		return "talkBig"
	}

	return mappedType
}

// =====================
// Parpadeo mejorado
// =====================

let isBlinking = false

function blinkOnce(duration = 120) {
	if (isBlinking) {
		return
	}

	isBlinking = true
	blinkEyeScaleY = 0.1

	setTimeout(() => {
		blinkEyeScaleY = 1
		isBlinking = false
	}, duration)
}

function doBlinkSequence() {
	blinkOnce(120)

	// Doble parpadeo ocasional.
	if (Math.random() < avatarPreset.doubleBlinkChance) {
		setTimeout(() => {
			blinkOnce(120)
		}, 170)
	}
}

function scheduleNextBlink() {
	const nextDelay = randomRange(avatarPreset.blinkMinMs, avatarPreset.blinkMaxMs)
	setTimeout(() => {
		doBlinkSequence()
		scheduleNextBlink()
	}, nextDelay)
}

scheduleNextBlink()

// =====================
// Bucle de render
// =====================

// =====================
// WebSocket con Python
// =====================

let socket = null
let wsReconnectTimer = null
const WS_URL = "ws://127.0.0.1:3312"

function scheduleWebSocketReconnect(delayMs = 1200) {
	if (wsReconnectTimer || socket) {
		return
	}

	wsReconnectTimer = setTimeout(() => {
		wsReconnectTimer = null
		connectWebSocket()
	}, delayMs)
}

function connectWebSocket() {
	if (socket) {
		return
	}

	socket = new WebSocket(WS_URL)

	socket.onopen = () => {
	}

	socket.onerror = (error) => {
		try {
			socket.close()
		} catch (closeError) {
		}
	}

	socket.onmessage = async (event) => {
		let data

		try {
			data = JSON.parse(event.data)
		} catch (error) {
			return
		}

		await ensureAudioRunning()

		// Capturar cambio de emoción
		if (data.emotion) {
			window.setAvatarEmotion(data.emotion)
			return
		}

		if (data.state === "speaking") {
			speaking = true
			bumpSpeakingWatchdog()
			return
		}

		if (data.state === "idle") {
			speaking = false
			
			// Cancelar timeout si existe
			clearSpeakingWatchdog()
			
			nextChunkTime = 0
			// Si el audio no esta desbloqueado aun, no borrar chunks para poder
			// reproducirlos cuando el usuario haga click y se active AudioContext.
			if (audioReady) {
				pendingChunks = []
			}
			idleExpressionType = ""
			idleExpressionUntil = 0
			return
		}

		if (data.type === "audio_start") {
			speaking = true
			bumpSpeakingWatchdog()

			const isReady = await ensureAudioRunning()
			if (audioContext && isReady) {
				nextChunkTime = audioContext.currentTime
				setTimeout(() => {
					processPendingChunks()
				}, 50)
			}
			return
		}

		if (data.type === "audio_chunk" && data.format === "pcm_f32le" && data.data) {
			bumpSpeakingWatchdog()
			playPcmFloatChunk(data.data, data.sample_rate || 22050, data.channels || 1)
			return
		}

		if (data.type === "audio_end") {
			// No forzar idle aquí: con audio local en Python, este evento puede
			// llegar antes de que termine la reproduccion real en parlantes.
			// El cierre correcto se hace con data.state === "idle".
			if (audioReady) {
				processPendingChunks()
			}
		}
	}

	socket.onclose = () => {
		speaking = false
		clearSpeakingWatchdog()
		pendingChunks = []
		socket = null
		scheduleWebSocketReconnect(1200)
	}
}

// =====================
// Auto-inicializacion al cargar
// =====================

window.addEventListener("load", async () => {
	try {
		const activateAudio = async () => {
			const activated = await unlockAudioFromGesture()
			if (!activated) {
				return
			}

			document.removeEventListener("click", activateAudio)
			document.removeEventListener("keydown", activateAudio)
			document.removeEventListener("touchstart", activateAudio)
		}

		document.addEventListener("click", activateAudio)
		document.addEventListener("keydown", activateAudio)
		document.addEventListener("touchstart", activateAudio)

		connectWebSocket()
	} catch (error) {
	}
})

// =====================
// Monitor de visibilidad
// =====================

document.addEventListener("visibilitychange", async () => {
	if (!document.hidden && audioReady && speaking) {
		await ensureAudioRunning()
	}
})

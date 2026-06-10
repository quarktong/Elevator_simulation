const app = getApp()

Page({
  data: {
    elevators: [],
    selectedFloor: null,
    currentTime: '--:--:--'
  },

  onLoad: function () {
    this.loadElevators()
    this.startTimeUpdate()
    this.startElevatorUpdate()
  },

  loadElevators: function() {
    this.setData({
      elevators: app.globalData.elevators
    })
  },

  startTimeUpdate: function() {
    this.updateTime()
    setInterval(() => {
      this.updateTime()
    }, 1000)
  },

  updateTime: function() {
    const now = new Date()
    const hours = now.getHours().toString().padStart(2, '0')
    const minutes = now.getMinutes().toString().padStart(2, '0')
    const seconds = now.getSeconds().toString().padStart(2, '0')
    this.setData({
      currentTime: `${hours}:${minutes}:${seconds}`
    })
  },

  startElevatorUpdate: function() {
    setInterval(() => {
      this.loadElevators()
    }, 1000)
  },

  getStatusText: function(status) {
    const texts = {
      'running': '运行中',
      'idle': '空闲',
      'door-open': '开门中'
    }
    return texts[status] || status
  },

  calculateETA: function(elevator, targetFloor) {
    return app.calculateETA(elevator, targetFloor)
  }
})
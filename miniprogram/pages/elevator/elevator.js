const app = getApp()

Page({
  data: {
    floors: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
    selectedFloor: null,
    callResult: null
  },

  onLoad: function () {
    console.log('呼叫电梯页面加载')
  },

  selectFloor: function(e) {
    const floor = parseInt(e.currentTarget.dataset.floor)
    
    this.setData({
      selectedFloor: floor
    })

    this.callElevator(floor)
  },

  callElevator: function(floor) {
    const elevator = app.callElevator(floor)
    
    if (elevator) {
      const eta = app.calculateETA(elevator, floor)
      
      this.setData({
        callResult: {
          name: elevator.name,
          currentFloor: elevator.floor,
          eta: eta
        }
      })

      wx.showToast({
        title: `已呼叫${elevator.name}前往${floor}层`,
        icon: 'success',
        duration: 2000
      })
    } else {
      wx.showToast({
        title: '呼叫失败',
        icon: 'error',
        duration: 2000
      })
    }
  }
})
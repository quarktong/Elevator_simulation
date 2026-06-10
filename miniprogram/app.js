App({
  globalData: {
    elevators: [
      { id: 1, name: 'E1', floor: 1, status: 'idle', direction: 'idle', passengers: 0 },
      { id: 2, name: 'E2', floor: 5, status: 'running', direction: 'up', passengers: 3 },
      { id: 3, name: 'E3', floor: 10, status: 'door-open', direction: 'idle', passengers: 5 },
      { id: 4, name: 'E4', floor: 15, status: 'running', direction: 'down', passengers: 2 }
    ],
    selectedFloor: null,
    systemStatus: 'normal'
  },

  onLaunch: function () {
    console.log('电梯监控小程序启动')
    this.startSimulation()
  },

  onShow: function () {
    console.log('小程序显示')
  },

  onHide: function () {
    console.log('小程序隐藏')
  },

  startSimulation: function() {
    setInterval(() => {
      this.updateElevators()
    }, 1000)
  },

  updateElevators: function() {
    const elevators = this.globalData.elevators
    
    elevators.forEach(elevator => {
      if (elevator.status === 'running') {
        if (elevator.direction === 'up') {
          elevator.floor = Math.min(elevator.floor + 1, 17)
          if (elevator.floor >= 17) {
            elevator.direction = 'down'
          }
        } else {
          elevator.floor = Math.max(elevator.floor - 1, 1)
          if (elevator.floor <= 1) {
            elevator.direction = 'up'
          }
        }
      } else if (elevator.status === 'door-open') {
        setTimeout(() => {
          elevator.status = 'running'
          elevator.direction = elevator.floor >= 17 ? 'down' : 'up'
        }, 2000)
      }
    })
  },

  callElevator: function(floor) {
    const elevators = this.globalData.elevators
    let bestElevator = null
    let minDistance = Infinity

    elevators.forEach(elevator => {
      const distance = Math.abs(elevator.floor - floor)
      if (distance < minDistance) {
        minDistance = distance
        bestElevator = elevator
      }
    })

    if (bestElevator) {
      bestElevator.status = 'running'
      bestElevator.direction = floor > bestElevator.floor ? 'up' : 'down'
    }

    this.globalData.selectedFloor = floor
    return bestElevator
  },

  calculateETA: function(elevator, targetFloor) {
    if (!elevator || elevator.floor === targetFloor) return 0
    
    const distance = Math.abs(elevator.floor - targetFloor)
    let eta = distance * 2

    if (elevator.status === 'door-open') {
      eta += 3
    }

    return eta
  }
})
export type JourneyMissionId = "orbit-tau-ceti" | "rendezvous" | "astrophage" | "trench-run" | "classroom"

export type JourneyWaypointState = "completed" | "current" | "upcoming"

export type JourneyMission = {
  id: JourneyMissionId
  order: number
  code: string
  title: string
  description: string
  progress: number
  camera: "orbit" | "flyby" | "close" | "chase" | "planetOrbit"
  panelSide: "left" | "right"
}

export const LAUNCH_PROGRESS = 0.018

export const journeyMissions: JourneyMission[] = [
  {
    id: "orbit-tau-ceti",
    order: 1,
    code: "01",
    title: "Orbit Tau Ceti",
    description:
      "Reach Tau Ceti and establish a stable observation orbit around the star.",
    progress: 0.205,
    camera: "orbit",
    panelSide: "right",
  },
  {
    id: "rendezvous",
    order: 2,
    code: "02",
    title: "Rocky & Ryland rendezvous",
    description:
      "Match velocity with the Hail Mary, align both ships, and complete the navigation handoff.",
    progress: 0.39,
    camera: "flyby",
    panelSide: "left",
  },
  {
    id: "astrophage",
    order: 3,
    code: "03",
    title: "Collect the astrophage",
    description:
      "Enter the drifting astrophage bloom and draw a viable sample stream into containment.",
    progress: 0.575,
    camera: "close",
    panelSide: "right",
  },
  {
    id: "trench-run",
    order: 4,
    code: "04",
    title: "Eridian Trench Run",
    description:
      "Thread the comet corridor at speed, banking through the only stable line home.",
    progress: 0.765,
    camera: "chase",
    panelSide: "left",
  },
  {
    id: "classroom",
    order: 5,
    code: "05",
    title: "Classroom",
    description:
      "Return to Erid, establish a stable observation orbit, and complete the final handoff.",
    progress: 0.965,
    camera: "planetOrbit",
    panelSide: "right",
  },
]

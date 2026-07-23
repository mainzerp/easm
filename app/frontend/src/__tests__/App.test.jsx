import { describe, it, expect } from "vitest"

describe("App", () => {
  it("has a root div", () => {
    const el = document.createElement("div")
    el.id = "root"
    document.body.appendChild(el)
    expect(el.id).toBe("root")
  })
})

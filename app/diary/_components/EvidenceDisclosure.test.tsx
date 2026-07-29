// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

const updateLock = vi.fn().mockResolvedValue(undefined);
const item = { memoryId: "m1", text: "점심 김밥", photoPath: null };

describe("EvidenceDisclosure", () => {
  it("기본은 닫혀 있고 원본을 보여주지 않는다", () => {
    render(<EvidenceDisclosure items={[item]} updateLock={updateLock} />);
    expect(
      screen.getByRole("button", { name: /무엇을 보고 썼는지/ }),
    ).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("점심 김밥")).not.toBeInTheDocument();
  });

  it("펼치면 원본과 원본 표식을 함께 보여준다", async () => {
    render(<EvidenceDisclosure items={[item]} updateLock={updateLock} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button", { name: "근거 접기" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByText("점심 김밥")).toBeInTheDocument();
    expect(screen.getByText("내가 남긴 기록")).toBeInTheDocument();
  });

  it("근거가 없으면 아무것도 렌더하지 않는다", () => {
    const { container } = render(
      <EvidenceDisclosure items={[]} updateLock={updateLock} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("토글 버튼이 44px 터치 타깃을 만족한다", () => {
    render(<EvidenceDisclosure items={[item]} updateLock={updateLock} />);
    expect(screen.getByRole("button").className).toContain("min-h-11");
  });
});

describe("사진 근거", () => {
  it("사진만 있는 기록도 근거로 보여준다", async () => {
    render(
      <EvidenceDisclosure
        items={[
          {
            memoryId: "m1",
            text: null,
            photoPath: "u1/a.png",
            photoUrl: "https://x/a.png",
          },
        ]}
        updateLock={updateLock}
      />,
    );
    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByRole("img", { name: "이 기록에 붙인 사진" })).toHaveAttribute(
      "src",
      "https://x/a.png",
    );
  });

  it("서명 URL이 없으면 이미지를 그리지 않는다", async () => {
    render(
      <EvidenceDisclosure
        items={[
          {
            memoryId: "m1",
            text: "글만",
            photoPath: "u1/a.png",
          },
        ]}
        updateLock={updateLock}
      />,
    );
    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByText("글만")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});

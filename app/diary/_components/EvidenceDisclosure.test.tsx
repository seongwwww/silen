// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

describe("EvidenceDisclosure", () => {
  it("기본은 닫혀 있고 원본을 보여주지 않는다", () => {
    render(<EvidenceDisclosure items={["점심 김밥"]} />);
    expect(screen.getByRole("button")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("점심 김밥")).not.toBeInTheDocument();
  });

  it("펼치면 원본과 원본 표식을 함께 보여준다", async () => {
    render(<EvidenceDisclosure items={["점심 김밥"]} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByText("점심 김밥")).toBeInTheDocument();
    expect(screen.getByText("내가 남긴 기록")).toBeInTheDocument();
  });

  it("근거가 없으면 아무것도 렌더하지 않는다", () => {
    const { container } = render(<EvidenceDisclosure items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("토글 버튼이 44px 터치 타깃을 만족한다", () => {
    render(<EvidenceDisclosure items={["점심 김밥"]} />);
    expect(screen.getByRole("button").className).toContain("min-h-11");
  });
});

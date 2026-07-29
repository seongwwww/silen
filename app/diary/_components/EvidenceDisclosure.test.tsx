// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

describe("EvidenceDisclosure", () => {
  it("기본은 닫혀 있고 원본을 보여주지 않는다", () => {
    render(<EvidenceDisclosure items={[{ text: "점심 김밥", photoPath: null }]} />);
    expect(screen.getByRole("button")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("점심 김밥")).not.toBeInTheDocument();
  });

  it("펼치면 원본과 원본 표식을 함께 보여준다", async () => {
    render(<EvidenceDisclosure items={[{ text: "점심 김밥", photoPath: null }]} />);
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
    render(<EvidenceDisclosure items={[{ text: "점심 김밥", photoPath: null }]} />);
    expect(screen.getByRole("button").className).toContain("min-h-11");
  });
});

describe("사진 근거", () => {
  it("사진만 있는 기록도 근거로 보여준다", async () => {
    render(
      <EvidenceDisclosure
        items={[{ text: null, photoPath: "u1/a.png", photoUrl: "https://x/a.png" }]}
      />,
    );
    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByRole("img", { name: "이 기록에 붙인 사진" })).toHaveAttribute(
      "src",
      "https://x/a.png",
    );
  });

  it("서명 URL이 없으면 이미지를 그리지 않는다", async () => {
    render(<EvidenceDisclosure items={[{ text: "글만", photoPath: "u1/a.png" }]} />);
    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByText("글만")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("서명 URL이 만료되면 깨진 이미지를 숨기고 다시 불러오기 안내를 남긴다", async () => {
    render(
      <EvidenceDisclosure
        items={[{ text: null, photoPath: "u1/a.png", photoUrl: "https://x/a.png" }]}
      />,
    );
    await userEvent.click(screen.getByRole("button"));

    fireEvent.error(screen.getByRole("img", { name: "이 기록에 붙인 사진" }));

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(
      screen.getByText("사진을 다시 보려면 화면을 새로고침해 주세요"),
    ).toBeInTheDocument();
  });
});

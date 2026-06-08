import { Composition } from "remotion";
import { BarChartRace } from "./BarChartRace";

export const RemotionRoot = () => {
  return (
    <Composition
      id="CityPriceRace"
      component={BarChartRace}
      durationInFrames={1050}
      fps={30}
      width={1080}
      height={720}
    />
  );
};

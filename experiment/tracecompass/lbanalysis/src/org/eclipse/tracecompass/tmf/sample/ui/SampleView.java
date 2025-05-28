
package org.eclipse.tracecompass.tmf.sample.ui;

import java.awt.Color;
import java.text.FieldPosition;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

import org.eclipse.swt.SWT;
import org.eclipse.swt.widgets.Composite;
import org.eclipse.swt.widgets.Display;
import org.eclipse.swtchart.Chart;
import org.eclipse.swtchart.IBarSeries;
import org.eclipse.swtchart.ISeries;
import org.eclipse.swtchart.ISeries.SeriesType;
import org.eclipse.swtchart.Range;
import org.eclipse.tracecompass.tmf.core.event.ITmfEvent;
import org.eclipse.tracecompass.tmf.core.event.ITmfEventField;
import org.eclipse.tracecompass.tmf.core.event.TmfEvent;
import org.eclipse.tracecompass.tmf.core.request.ITmfEventRequest;
import org.eclipse.tracecompass.tmf.core.request.TmfEventRequest;
import org.eclipse.tracecompass.tmf.core.signal.TmfSignalHandler;
import org.eclipse.tracecompass.tmf.core.signal.TmfTimestampFormatUpdateSignal;
import org.eclipse.tracecompass.tmf.core.signal.TmfTraceSelectedSignal;
import org.eclipse.tracecompass.tmf.core.timestamp.TmfTimeRange;
import org.eclipse.tracecompass.tmf.core.timestamp.TmfTimestampFormat;
import org.eclipse.tracecompass.tmf.core.trace.ITmfTrace;
import org.eclipse.tracecompass.tmf.core.trace.TmfTraceManager;
import org.eclipse.tracecompass.tmf.ui.viewers.xychart.TmfChartTimeStampFormat;
import org.eclipse.tracecompass.tmf.ui.views.TmfView;
import org.eclipse.ui.part.ViewPart;

import java.io.BufferedWriter;
import java.io.FileOutputStream;
import java.io.FileWriter;
import java.io.IOException;

public class SampleView extends TmfView {

	private static final String SERIES_NAME = "Series";
	private static final String Y_AXIS_TITLE = "Total Execution Time";
	private static final String X_AXIS_TITLE = "Thread Number";
	private static final String FIELD = "value"; // The name of the field that we want to display on the Y axis
	private static final String VIEW_ID = "org.eclipse.tracecompass.tmf.sample.ui.view";
	private Chart chart;
	private ITmfTrace currentTrace;
	double minY = Double.MAX_VALUE, maxY = Double.MIN_VALUE;

	private static final int MAX_THREADS = 20;

	private double[] startTimes = new double[MAX_THREADS];
	private double[] endTimes = new double[MAX_THREADS];

	// a new map to record each thread separately
	private Map<Long, Integer>[] threadParallelRegionCounts;

	private Map<Long, Double>[] threadExecutionTimes;

	public SampleView() {
		super(VIEW_ID);

		threadParallelRegionCounts = new HashMap[MAX_THREADS];
		threadExecutionTimes = new HashMap[MAX_THREADS];

		for (int i = 0; i < MAX_THREADS; i++) {
			threadParallelRegionCounts[i] = new HashMap<>();
			threadExecutionTimes[i] = new HashMap<>();
		}

	}

	@Override
	public void createPartControl(Composite parent) {
		chart = new Chart(parent, SWT.BORDER);
		chart.setForeground(Display.getDefault().getSystemColor(SWT.COLOR_WHITE));
		chart.getTitle().setVisible(false);
		chart.getAxisSet().getXAxis(0).getTitle().setText(X_AXIS_TITLE);
		chart.getAxisSet().getXAxis(0).getTitle().setForeground(Display.getDefault().getSystemColor(SWT.COLOR_CYAN));
		chart.getAxisSet().getYAxis(0).getTitle().setText(Y_AXIS_TITLE);
		chart.getAxisSet().getYAxis(0).getTitle().setForeground(Display.getDefault().getSystemColor(SWT.COLOR_CYAN));
		chart.getSeriesSet().createSeries(SeriesType.BAR, SERIES_NAME);
		chart.getLegend().setVisible(false);

		chart.getAxisSet().getYAxis(0).getTick().setFormat(new TmfChartTimeStampFormat());
		chart.getAxisSet().getYAxis(0).getTick().setForeground(Display.getDefault().getSystemColor(SWT.COLOR_CYAN));
		chart.getAxisSet().getXAxis(0).getTick().setForeground(Display.getDefault().getSystemColor(SWT.COLOR_CYAN));

		chart.getAxisSet().getXAxis(0).getTitle().setText("Thread Number");
		chart.getAxisSet().getYAxis(0).getTitle().setText("Execution Time");

		chart.getLegend().setVisible(false);
		chart.getAxisSet().adjustRange();

	}

	public class TmfChartTimeStampFormat extends SimpleDateFormat {
		private static final long serialVersionUID = 1L;

		@Override
		public StringBuffer format(Date date, StringBuffer toAppendTo, FieldPosition fieldPosition) {
			long time = date.getTime();
			toAppendTo.append(TmfTimestampFormat.getDefaulTimeFormat().format(time));
			return toAppendTo;
		}
	}

	@TmfSignalHandler
	public void traceSelected(final TmfTraceSelectedSignal signal) {
		if (currentTrace == signal.getTrace()) {
			return;
		}
		currentTrace = signal.getTrace();

		// Create the request to get data from the trace
		TmfEventRequest req = new TmfEventRequest(TmfEvent.class, TmfTimeRange.ETERNITY, 0, ITmfEventRequest.ALL_DATA,
				ITmfEventRequest.ExecutionType.BACKGROUND) {

			ArrayList<Double> xValues = new ArrayList<>();
			ArrayList<Double> yValues = new ArrayList<>();

			Map<Integer, Double> threadsTime = new TreeMap<Integer, Double>();

			@Override
			public void handleData(ITmfEvent data) {

				super.handleData(data);
				ITmfEventField field = data.getContent().getField();
				String eventName = data.getName();

				if (field == null)
					return;

				int threadNum = extractThreadNumber(field);
				long parallelCodePtr = extractParallelCodePtr(field);

				if (threadNum == -1 || threadNum >= MAX_THREADS || parallelCodePtr == -1) {
					return;
				}

				if (eventName.equals("ompt_pinsight_lttng_ust:implicit_task_begin")) {

					startTimes[threadNum] = (double) data.getTimestamp().getValue();

					threadParallelRegionCounts[threadNum].put(parallelCodePtr,
							threadParallelRegionCounts[threadNum].getOrDefault(parallelCodePtr, 0) + 1);

				} else if (eventName.equals("ompt_pinsight_lttng_ust:implicit_task_end")) {

					endTimes[threadNum] = (double) data.getTimestamp().getValue();

					// Calculate execution time for the thread
					double executionTime = endTimes[threadNum] - startTimes[threadNum];

					threadExecutionTimes[threadNum].put(parallelCodePtr, executionTime);

				}

			}

			@Override
			public void handleSuccess() {
				super.handleSuccess();

				List<String> xCategoryList = new ArrayList<>();
				Map<Long, double[]> ySeriesMap = new HashMap<>();

				int threadCount = threadExecutionTimes.length;
				double[] x = new double[threadCount];

				for (int i = 0; i < threadCount; i++) {
					x[i] = i;
					xCategoryList.add("Thread " + i);

					Map<Long, Double> phases = threadExecutionTimes[i];
					for (Map.Entry<Long, Double> entry : phases.entrySet()) {
						long ptr = entry.getKey();
						double execTime = entry.getValue();
						ySeriesMap.computeIfAbsent(ptr, k -> new double[threadCount])[i] = execTime;
					}
				}

				System.out.println("Parallel Region Execution Counts Per Thread:");

				for (int threadNum = 0; threadNum < MAX_THREADS; threadNum++) {
					if (!threadParallelRegionCounts[threadNum].isEmpty()) {
						System.out.println("Thread " + threadNum + ":");
						for (Map.Entry<Long, Integer> entry : threadParallelRegionCounts[threadNum].entrySet()) {
							System.out.println(" Parallel Region 0x" + Long.toHexString(entry.getKey()) + " executed "
									+ entry.getValue() + " times");
						}
					}
				}

				String[] xCategories = xCategoryList.toArray(new String[0]);

				Display.getDefault().asyncExec(() -> {
					// Remove all existing series first
					Arrays.stream(chart.getSeriesSet().getSeries())
							.forEach(s -> chart.getSeriesSet().deleteSeries(s.getId()));

					// Setup x-axis categories before assigning series
					chart.getAxisSet().getXAxis(0).enableCategory(true);
					chart.getAxisSet().getXAxis(0).setCategorySeries(xCategories);
					chart.getAxisSet().getXAxis(0).setRange(new Range(-1, threadCount));

					// Add new series (stacked per parallel region)
					int colorIndex = 0;
					for (Map.Entry<Long, double[]> entry : ySeriesMap.entrySet()) {
						IBarSeries barSeries = (IBarSeries) chart.getSeriesSet().createSeries(SeriesType.BAR,
								"Region 0x" + Long.toHexString(entry.getKey()));
						barSeries.setXSeries(x);
						barSeries.setYSeries(entry.getValue());
						barSeries
								.setBarColor(Display.getDefault().getSystemColor((SWT.COLOR_GREEN + (colorIndex % 8))));
						barSeries.enableStack(true);
						colorIndex++;
					}

					chart.getAxisSet().adjustRange();
					chart.redraw();

					exportToExcel(threadExecutionTimes);
					
					
					// swtchart built in zooming
					chart.addListener(SWT.MouseWheel, event -> {
					    if (event.count > 0) {
					        chart.getAxisSet().zoomIn();
					    } else {
					        chart.getAxisSet().zoomOut();
					    }
					});
					
					
					chart.getPlotArea().addMouseMoveListener(e -> {
						double mouseX = chart.getAxisSet().getXAxis(0).getDataCoordinate(e.x);
						double mouseY = chart.getAxisSet().getYAxis(0).getDataCoordinate(e.y);

						int closestThread = (int) Math.round(mouseX);
						if (closestThread < 0 || closestThread >= MAX_THREADS) {
							chart.getPlotArea().setToolTipText(null);
							return;
						}

						double cumulativeHeight = 0.0;

						ISeries[] allSeries = chart.getSeriesSet().getSeries();

						for (int i = allSeries.length - 1; i >= 0; i--) {
							if (allSeries[i] instanceof IBarSeries) {
								IBarSeries barSeries = (IBarSeries) allSeries[i];
								double[] ySeries = barSeries.getYSeries();

								if (closestThread < ySeries.length) {
									double barHeight = ySeries[closestThread];
									double topBoundary = cumulativeHeight + barHeight;
									double bottomBoundary = cumulativeHeight;

									if (mouseY >= bottomBoundary && mouseY <= topBoundary) {
										chart.getPlotArea()
												.setToolTipText("Thread " + closestThread + "\nParallel Region: "
														+ barSeries.getId() + "\nExecution Time: " + barHeight + " ms");
										return;
									}
									cumulativeHeight = topBoundary;
								}
							}
						}

						chart.getPlotArea().setToolTipText(null);
					});
				});
			}

			private int findClosestIndex(double mouseX, double[] xValues) {
				int closestIndex = -1;
				double minDiff = Double.MAX_VALUE;

				for (int i = 0; i < xValues.length; i++) {
					double diff = Math.abs(mouseX - xValues[i]);
					if (diff < minDiff) {
						minDiff = diff;
						closestIndex = i;
					}
				}
				return closestIndex;
			}

			private int extractThreadNumber(ITmfEventField field) {
				String fieldString = field.toString();
				String[] contentSplit = fieldString.split("\\s*,\\s*");
				for (String content : contentSplit) {
					if (content.contains("omp_thread_num")) {
						String[] Numsplit = content.split("\\s*=\\s*");
						return Integer.parseInt(Numsplit[1]);
					}
				}
				return -1;
			}

			private long extractParallelCodePtr(ITmfEventField field) {
				String fieldString = field.toString();
				String[] contentSplit = fieldString.split("\\s*,\\s*");
				for (String content : contentSplit) {
					if (content.contains("parallel_codeptr")) {
						String[] split = content.split("\\s*=\\s*");
						try {
							return Long.parseUnsignedLong(split[1].replace("0x", ""), 16);
						} catch (NumberFormatException e) {
							System.err.println("Invalid parallel_codeptr value: " + split[1]);
							return -1;
						}
					}
				}
				return -1;
			}

			private double[] toArray(List<Double> list) {
				double[] d = new double[list.size()];
				for (int i = 0; i < list.size(); ++i) {
					d[i] = list.get(i);
				}
				return d;
			}
		};

		ITmfTrace trace = signal.getTrace();
		trace.sendRequest(req);
	}

	@Override
	public void setFocus() {
		chart.setFocus();
	}

	private void exportToExcel(Map<Long, Double>[] threadExecutionTimes) {
		String originalFormatPath = "/Users/bhavanachappidi/Downloads/parallel_thread_times_original.csv";
		String matrixFormatPath = "/Users/bhavanachappidi/Downloads/parallel_thread_times_matrix.csv";
		
		BufferedWriter originalWriter = null;
		BufferedWriter matrixWriter = null;
		
		try {
			originalWriter = new BufferedWriter(new FileWriter(originalFormatPath));
			matrixWriter = new BufferedWriter(new FileWriter(matrixFormatPath));

			originalWriter.write("Thread#,Parallel Region,Execution Time");
	        	originalWriter.newLine();

			Set<Long> allParallelRegions = new TreeSet<>();
			for (Map<Long, Double> threadData : threadExecutionTimes) {
				allParallelRegions.addAll(threadData.keySet());
	        	}
			
			matrixWriter.write("Thread#");
			for (Long region : allParallelRegions) {
	            		matrixWriter.write("," + region);
	        	}
	        	matrixWriter.newLine();

			// Processing data
			for (int threadNum = 0; threadNum < threadExecutionTimes.length; threadNum++) {

				// Get execution times for each parallel_codeptr in this thread
				Map<Long, Double> threadData = threadExecutionTimes[threadNum];
				if (threadData.isEmpty()) {
	                		continue;
	            		}
				matrixWriter.write(String.valueOf(threadNum));
				
				for (Long region : allParallelRegions) {
					Double executionTime = threadData.get(region);

					matrixWriter.write("," + (executionTime != null ? executionTime : ""));
					if (executionTime != null) {
	                    			originalWriter.write(threadNum + "," + region + "," + executionTime);
	                    			originalWriter.newLine();
	                		}

				}
				matrixWriter.newLine();
			}

			System.out.println("CSV files created successfully!");
			System.out.println("Original format: " + originalFormatPath);
	        	System.out.println("Matrix format: " + matrixFormatPath);
		} catch (IOException e) {
			e.printStackTrace();
		} finally {
			try {
				if (originalWriter != null) {
					originalWriter.close();
				}
				if (matrixWriter != null) {
					matrixWriter.close();
				}
			} catch (IOException e) {
				e.printStackTrace();
			}
		}
	}

}
